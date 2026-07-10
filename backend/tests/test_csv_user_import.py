"""POST /v1/users/import-csv — import en masse de comptes depuis un CSV d'ERP par un admin,
avec envoi d'un email de création de mot de passe à chaque utilisateur créé."""
import os
import secrets

import models

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _make_admin_client(client):
    client.post(
        "/v1/setup-admin",
        json={
            "username": "csv_admin", "email": "csv_admin@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "csv_admin@example.com", "password": _TEST_PASSWORD})
    client.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
    return client


def _make_regular_client(client, mark_verified):
    client.post("/v1/register", json={
        "username": "csv_user", "email": "csv_user@example.com",
        "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })
    mark_verified("csv_user@example.com")
    resp = client.post("/v1/login", json={"email": "csv_user@example.com", "password": _TEST_PASSWORD})
    client.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
    return client


def _upload(client, csv_text: str):
    return client.post(
        "/v1/users/import-csv",
        files={"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")},
    )


class TestPermissions:
    def test_regular_user_forbidden(self, client, mark_verified):
        auth_client = _make_regular_client(client, mark_verified)
        resp = _upload(auth_client, "email,username,prenom,nom\na@example.com,a_user,A,A\n")
        assert resp.status_code == 403

    def test_unauthenticated_forbidden(self, client):
        resp = _upload(client, "email,username,prenom,nom\na@example.com,a_user,A,A\n")
        assert resp.status_code == 401


class TestImport:
    def test_creates_users_and_reports_count(self, client):
        admin_client = _make_admin_client(client)
        csv_text = (
            "email,username,prenom,nom\n"
            "alice@example.com,alice,Alice,Dupont\n"
            "bob@example.com,bob,Bob,Martin\n"
        )
        resp = _upload(admin_client, csv_text)
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["total_rows"] == 2
        assert data["created"] == 2
        assert data["skipped"] == []

    def test_created_user_has_user_role_and_is_verified(self, client, db_session):
        admin_client = _make_admin_client(client)
        _upload(admin_client, "email,username,prenom,nom\ncarol@example.com,carol,Carol,Petit\n")

        user = db_session.query(models.Utilisateur).filter_by(email="carol@example.com").first()
        assert user is not None
        assert user.email_verified is True
        assert user.role.nom_role == "user"

    def test_missing_required_columns_returns_400(self, client):
        admin_client = _make_admin_client(client)
        resp = _upload(admin_client, "prenom,nom\nAlice,Dupont\n")
        assert resp.status_code == 400

    def test_invalid_email_row_is_skipped(self, client):
        admin_client = _make_admin_client(client)
        csv_text = "email,username,prenom,nom\nnot-an-email,dave,Dave,Petit\n"
        resp = _upload(admin_client, csv_text)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 0
        assert len(data["skipped"]) == 1
        assert data["skipped"][0]["reason"] == "email ou username invalide"

    def test_duplicate_within_file_is_skipped(self, client):
        admin_client = _make_admin_client(client)
        csv_text = (
            "email,username,prenom,nom\n"
            "eve@example.com,eve,Eve,Petit\n"
            "eve@example.com,eve2,Eve,Petit\n"
        )
        resp = _upload(admin_client, csv_text)
        data = resp.json()
        assert data["created"] == 1
        assert len(data["skipped"]) == 1
        assert data["skipped"][0]["reason"] == "doublon dans le fichier"

    def test_existing_email_is_skipped(self, client, mark_verified):
        client.post("/v1/register", json={
            "username": "frank", "email": "frank@example.com",
            "password": _TEST_PASSWORD, "prenom": "F", "nom": "N",
        })
        mark_verified("frank@example.com")

        admin_client = _make_admin_client(client)
        resp = _upload(admin_client, "email,username,prenom,nom\nfrank@example.com,frank2,F,N\n")
        data = resp.json()
        assert data["created"] == 0
        assert data["skipped"][0]["reason"] == "email déjà utilisé"

    def test_soft_deleted_account_email_is_still_skipped(self, client, mark_verified, db_session):
        """Même raison que le fix appliqué à /register : la contrainte UNIQUE en base
        s'applique aussi aux comptes soft-deleted pas encore purgés (RGPD, 30j)."""
        client.post("/v1/register", json={
            "username": "ghost", "email": "ghost@example.com",
            "password": _TEST_PASSWORD, "prenom": "G", "nom": "H",
        })
        mark_verified("ghost@example.com")
        user = db_session.query(models.Utilisateur).filter_by(email="ghost@example.com").first()
        from datetime import datetime
        user.deleted_at = datetime.utcnow()
        db_session.commit()

        admin_client = _make_admin_client(client)
        resp = _upload(admin_client, "email,username,prenom,nom\nghost@example.com,ghost2,G,H\n")
        data = resp.json()
        assert data["created"] == 0
        assert data["skipped"][0]["reason"] == "email déjà utilisé"

    def test_row_limit_enforced(self, client, monkeypatch):
        monkeypatch.setattr("routers.users.MAX_CSV_IMPORT_ROWS", 1)
        admin_client = _make_admin_client(client)
        csv_text = "email,username,prenom,nom\na@example.com,a_user,A,A\nb@example.com,b_user,B,B\n"
        resp = _upload(admin_client, csv_text)
        assert resp.status_code == 400
