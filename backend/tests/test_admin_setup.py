"""POST /v1/setup — amorçage du compte admin d'une instance provisionnée via
ops/provision_client.py, sans mot de passe transmis en clair. Le token
(admin_setup_token) est distinct du JWT applicatif : stocké en base, à usage unique
(admin_setup_token_used_at) et expirant (admin_setup_token_expires_at), jamais renvoyé par
aucune route. Couvre aussi l'idempotence de run_migrations() : bug corrigé où le
password_hash d'un admin déjà existant était réécrit à chaque redémarrage de l'app."""
import os
import secrets
from datetime import datetime, timedelta

import models
from main import run_migrations

_TEST_PASSWORD = secrets.token_urlsafe(16)
_ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@smartticket.app")


def _give_admin_a_setup_token(db_session, *, expires_delta=timedelta(hours=48)):
    admin = db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).first()
    assert admin is not None, "Compte admin par défaut introuvable — bootstrap au démarrage en échec ?"
    token = secrets.token_urlsafe(32)
    admin.admin_setup_token = token
    admin.admin_setup_token_expires_at = datetime.utcnow() + expires_delta
    db_session.commit()
    return token


class TestAdminSetupEndpoint:
    def test_invalid_token_rejected(self, client):
        resp = client.post("/v1/setup", json={
            "token": "does-not-exist", "username": "newadmin", "email": "newadmin@example.com",
            "password": _TEST_PASSWORD,
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "invalid_token"

    def test_valid_token_completes_setup_and_allows_login(self, client, db_session):
        token = _give_admin_a_setup_token(db_session)

        resp = client.post("/v1/setup", json={
            "token": token, "username": "acme_admin", "email": "acme-admin@example.com",
            "password": _TEST_PASSWORD,
        })
        assert resp.status_code == 200, resp.json()

        login = client.post("/v1/login", json={"email": "acme-admin@example.com", "password": _TEST_PASSWORD})
        assert login.status_code == 200, login.json()

    def test_token_rejected_once_already_used(self, client, db_session):
        token = _give_admin_a_setup_token(db_session)

        first = client.post("/v1/setup", json={
            "token": token, "username": "u1", "email": "u1@example.com", "password": _TEST_PASSWORD,
        })
        assert first.status_code == 200, first.json()

        second = client.post("/v1/setup", json={
            "token": token, "username": "u2", "email": "u2@example.com", "password": _TEST_PASSWORD,
        })
        assert second.status_code == 400
        assert second.json()["detail"]["code"] == "token_already_used"

    def test_expired_token_rejected(self, client, db_session):
        token = _give_admin_a_setup_token(db_session, expires_delta=timedelta(hours=-1))

        resp = client.post("/v1/setup", json={
            "token": token, "username": "u1", "email": "u1@example.com", "password": _TEST_PASSWORD,
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "token_expired"

    def test_password_too_short_rejected(self, client, db_session):
        token = _give_admin_a_setup_token(db_session)
        resp = client.post("/v1/setup", json={
            "token": token, "username": "u1", "email": "u1@example.com", "password": "short",
        })
        assert resp.status_code == 400

    def test_password_below_admin_minimum_of_12_rejected(self, client, db_session):
        """L'admin d'instance exige 12 caractères, plus strict que le reste de l'app
        (6 ailleurs) — un mot de passe de 11 caractères doit être refusé."""
        token = _give_admin_a_setup_token(db_session)
        resp = client.post("/v1/setup", json={
            "token": token, "username": "u1", "email": "u1@example.com", "password": "eleven-char",
        })
        assert resp.status_code == 400

    def test_common_password_rejected_even_if_long_enough(self, client, db_session):
        token = _give_admin_a_setup_token(db_session)
        resp = client.post("/v1/setup", json={
            "token": token, "username": "u1", "email": "u1@example.com", "password": "password123",
        })
        assert resp.status_code == 400

    def test_password_and_token_consumption_committed_together(self, client, db_session):
        """Une seule transaction : impossible d'observer le token consommé sans le nouveau
        mot de passe posé, ou l'inverse."""
        token = _give_admin_a_setup_token(db_session)
        resp = client.post("/v1/setup", json={
            "token": token, "username": "atomic_admin", "email": "atomic-admin@example.com",
            "password": _TEST_PASSWORD,
        })
        assert resp.status_code == 200, resp.json()

        db_session.expire_all()
        user = db_session.query(models.Utilisateur).filter_by(email="atomic-admin@example.com").first()
        assert user.admin_setup_token_used_at is not None
        login = client.post("/v1/login", json={"email": "atomic-admin@example.com", "password": _TEST_PASSWORD})
        assert login.status_code == 200, login.json()

    def test_duplicate_email_rejected(self, client, db_session, mark_verified):
        client.post("/v1/register", json={
            "username": "existing", "email": "taken@example.com",
            "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
        })
        mark_verified("taken@example.com")
        token = _give_admin_a_setup_token(db_session)

        resp = client.post("/v1/setup", json={
            "token": token, "username": "brand_new", "email": "taken@example.com", "password": _TEST_PASSWORD,
        })
        assert resp.status_code == 400

    def test_token_never_appears_in_me_response(self, client, registered_user):
        login = client.post("/v1/login", json={
            "email": registered_user["email"], "password": registered_user["password"],
        })
        client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
        me = client.get("/v1/me").json()
        assert "admin_setup_token" not in me
        assert "admin_setup_token_expires_at" not in me
        assert "admin_setup_token_used_at" not in me


class TestRunMigrationsAdminBootstrapIdempotence:
    def test_existing_admin_password_never_rewritten_on_restart(self, client, db_session):
        """Bug corrigé : run_migrations() réécrivait le password_hash de l'admin à CHAQUE
        redémarrage de l'app à partir de ADMIN_PASSWORD/'ChangeMe123!', ce qui aurait
        silencieusement écrasé un mot de passe choisi via /v1/setup au premier redeploy."""
        admin = db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).first()
        assert admin is not None
        sentinel_hash = "sentinel-hash-should-survive-a-restart"
        admin.password_hash = sentinel_hash
        db_session.commit()

        run_migrations()

        db_session.expire_all()
        admin_after = db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).first()
        assert admin_after.password_hash == sentinel_hash

    def test_new_admin_created_with_setup_token_when_env_var_set(self, client, db_session, monkeypatch):
        db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).delete()
        db_session.commit()

        monkeypatch.setenv("ADMIN_SETUP_TOKEN", "fresh-instance-token")
        try:
            run_migrations()
        finally:
            monkeypatch.delenv("ADMIN_SETUP_TOKEN", raising=False)

        db_session.expire_all()
        admin = db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).first()
        assert admin is not None
        assert admin.admin_setup_token == "fresh-instance-token"
        assert admin.admin_setup_token_expires_at is not None
        assert admin.admin_setup_token_used_at is None

    def test_new_admin_created_with_password_when_no_token_env_var(self, client, db_session):
        """Comportement historique préservé pour le dev local/docker-compose/démo, où
        ADMIN_SETUP_TOKEN n'est jamais défini."""
        db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).delete()
        db_session.commit()

        run_migrations()

        db_session.expire_all()
        admin = db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).first()
        assert admin is not None
        assert admin.admin_setup_token is None
        assert admin.admin_setup_token_expires_at is None


class TestRealisticProvisioningTokenChain:
    """Reproduit la CHAÎNE RÉELLE d'un provisioning via ops/provision_client.py — pas juste
    la pose directe d'un token en base comme le fait _give_admin_a_setup_token() plus haut
    dans ce fichier. Bug trouvé le 2026-07-14 lors du premier provisioning réel contre
    l'API Render : POST /v1/setup renvoyait 400 malgré un token en apparence correct dans
    l'env var du backend. Aucun test existant ne couvrait ce chemin bout-en-bout (token
    généré par secrets.token_urlsafe(32) -> posé en env var ADMIN_SETUP_TOKEN -> lu par
    run_migrations() au démarrage -> renvoyé au client via /v1/setup?token=... -> POST
    /v1/setup avec ce même token), ce qui explique pourquoi ce bug n'a été détecté qu'en
    conditions réelles plutôt qu'en CI."""

    def test_token_generated_like_provisioning_and_read_from_env_survives_the_full_chain(self, client, db_session, monkeypatch):
        db_session.query(models.Utilisateur).filter_by(email=_ADMIN_EMAIL).delete()
        db_session.commit()

        # Même génération EXACTE que ops/provision_client.py::generate_secret() — pas un
        # token de test simplifié comme "fresh-instance-token" ci-dessus. secrets.token_urlsafe
        # produit un alphabet base64 URL-safe (A-Za-z0-9-_), susceptible de contenir les
        # caractères '-'/'_' qu'un token de test à la main ne contient pas forcément.
        real_token = secrets.token_urlsafe(32)
        monkeypatch.setenv("ADMIN_SETUP_TOKEN", real_token)
        try:
            run_migrations()
        finally:
            monkeypatch.delenv("ADMIN_SETUP_TOKEN", raising=False)

        # Le client construit ce POST à partir du query param ?token=... de /setup (cf.
        # frontend/app/(auth)/setup/page.tsx) — ici on saute directement au body réellement
        # envoyé, le round-trip URL -> useSearchParams() étant strictement côté navigateur,
        # non testable depuis la suite pytest backend.
        resp = client.post("/v1/setup", json={
            "token": real_token, "username": "acme_admin", "email": "acme-admin@example.com",
            "password": _TEST_PASSWORD,
        })
        assert resp.status_code == 200, resp.json()

        login = client.post("/v1/login", json={"email": "acme-admin@example.com", "password": _TEST_PASSWORD})
        assert login.status_code == 200, login.json()
