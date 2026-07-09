"""Tests du chat anonyme B2B2C : POST /v1/sessions/guest crée un compte invité silencieux,
POST /v1/me/claim le transforme en compte réel."""
import os
import secrets
from datetime import datetime, timedelta

import models
from main import purge_unclaimed_guests

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_admin_token(client) -> str:
    client.post(
        "/v1/setup-admin",
        json={
            "username": "guest_test_admin", "email": "guest_test_admin@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "guest_test_admin@example.com", "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


class TestCreateGuestSession:
    def test_creates_a_usable_session_without_prior_registration(self, client):
        resp = client.post("/v1/sessions/guest")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "session" in data
        assert data["session"]["status"] == "open"
        # Le cookie doit être posé pour que les requêtes suivantes du navigateur
        # (sans repasser le token en Authorization) soient déjà authentifiées.
        assert "auth_token" in resp.cookies

    def test_guest_can_immediately_read_their_own_profile(self, client):
        token = client.post("/v1/sessions/guest").json()["access_token"]
        resp = client.get("/v1/me", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"
        assert data["email_verified"] is True
        assert data["is_guest"] is True

    def test_guest_can_send_a_message_in_their_session(self, client):
        guest = client.post("/v1/sessions/guest").json()
        token, session_id = guest["access_token"], guest["session"]["id"]
        resp = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "user", "contenu": "Bonjour, j'ai un souci.",
        }, headers=_auth(token))
        assert resp.status_code == 201

    def test_a_registered_user_is_never_flagged_as_guest(self, client, registered_user):
        token = client.post("/v1/login", json={
            "email": registered_user["email"], "password": registered_user["password"],
        }).json()["access_token"]
        resp = client.get("/v1/me", headers=_auth(token))
        assert resp.json()["is_guest"] is False


class TestClaimGuestAccount:
    def test_claim_sets_real_email_and_password(self, client):
        guest_token = client.post("/v1/sessions/guest").json()["access_token"]
        resp = client.post("/v1/me/claim", json={
            "email": "claimed@example.com", "password": "a-real-password-123",
        }, headers=_auth(guest_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "claimed@example.com"
        assert data["is_guest"] is False
        assert data["email_verified"] is False  # nouvelle adresse, à reconfirmer

    def test_claim_reissues_a_working_session_cookie(self, client):
        guest_token = client.post("/v1/sessions/guest").json()["access_token"]
        claim_resp = client.post("/v1/me/claim", json={
            "email": "reissue@example.com", "password": "a-real-password-123",
        }, headers=_auth(guest_token))
        assert claim_resp.status_code == 200
        # Le cookie fraîchement réémis (email à jour) doit fonctionner immédiatement,
        # sans que le navigateur ait besoin de se reconnecter.
        me_resp = client.get("/v1/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "reissue@example.com"

    def test_cannot_claim_an_already_used_email(self, client, registered_user):
        guest_token = client.post("/v1/sessions/guest").json()["access_token"]
        resp = client.post("/v1/me/claim", json={
            "email": registered_user["email"], "password": "a-real-password-123",
        }, headers=_auth(guest_token))
        assert resp.status_code == 400

    def test_claim_rejects_short_password(self, client):
        guest_token = client.post("/v1/sessions/guest").json()["access_token"]
        resp = client.post("/v1/me/claim", json={
            "email": "shortpw2@example.com", "password": "abc",
        }, headers=_auth(guest_token))
        assert resp.status_code == 400

    def test_non_guest_account_cannot_use_claim(self, client, auth_client):
        resp = auth_client.post("/v1/me/claim", json={
            "email": "hijack@example.com", "password": "a-real-password-123",
        })
        assert resp.status_code == 400


class TestGuestAccountsHiddenFromAdmin:
    def test_guest_accounts_excluded_from_user_listing(self, client):
        client.post("/v1/sessions/guest")
        admin_token = _make_admin_token(client)
        resp = client.get("/v1/users", params={"role": "user"}, headers=_auth(admin_token))
        assert resp.status_code == 200
        assert all("guest" not in u["email"] for u in resp.json())


class TestPurgeUnclaimedGuests:
    def test_old_unclaimed_guest_is_soft_deleted_along_with_its_session(self, client, db_session):
        guest = client.post("/v1/sessions/guest").json()
        user_id, session_id = guest["user_id"], guest["session"]["id"]

        # Antidate la création pour simuler un compte invité abandonné depuis longtemps.
        user_row = db_session.query(models.Utilisateur).filter_by(id=user_id).first()
        user_row.date_creation = datetime.utcnow() - timedelta(days=30)
        db_session.commit()

        purge_unclaimed_guests(ttl_days=7)

        db_session.expire_all()
        purged_user = db_session.query(models.Utilisateur).filter_by(id=user_id).first()
        purged_session = db_session.query(models.ChatSession).filter_by(id=session_id).first()
        assert purged_user.deleted_at is not None
        assert purged_session.deleted_at is not None

    def test_recent_unclaimed_guest_is_not_purged(self, client, db_session):
        guest = client.post("/v1/sessions/guest").json()
        purge_unclaimed_guests(ttl_days=7)
        db_session.expire_all()
        untouched = db_session.query(models.Utilisateur).filter_by(id=guest["user_id"]).first()
        assert untouched.deleted_at is None

    def test_claimed_guest_is_never_purged_even_if_old(self, client, db_session):
        guest = client.post("/v1/sessions/guest").json()
        client.post("/v1/me/claim", json={
            "email": "claimed-old@example.com", "password": "a-real-password-123",
        }, headers=_auth(guest["access_token"]))

        user_row = db_session.query(models.Utilisateur).filter_by(id=guest["user_id"]).first()
        user_row.date_creation = datetime.utcnow() - timedelta(days=30)
        db_session.commit()

        purge_unclaimed_guests(ttl_days=7)

        db_session.expire_all()
        untouched = db_session.query(models.Utilisateur).filter_by(id=guest["user_id"]).first()
        assert untouched.deleted_at is None
