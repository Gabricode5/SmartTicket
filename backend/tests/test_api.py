"""Integration tests for FastAPI endpoints."""
import secrets
from datetime import datetime

import models

_TEST_PASSWORD = secrets.token_urlsafe(16)


class TestRoot:
    def test_health_check(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "Online"


class TestRegister:
    def test_creates_user_with_correct_fields(self, client):
        resp = client.post("/v1/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": _TEST_PASSWORD,
            "prenom": "Alice",
            "nom": "Dupont",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@example.com"
        assert data["username"] == "alice"
        assert data["role"] == "user"
        assert "password" not in data
        assert "password_hash" not in data

    def test_duplicate_email_returns_400(self, client):
        payload = {
            "username": "bob",
            "email": "bob@example.com",
            "password": _TEST_PASSWORD,
            "prenom": "Bob",
            "nom": "Martin",
        }
        client.post("/v1/register", json=payload)
        resp = client.post("/v1/register", json={**payload, "username": "bob2"})
        assert resp.status_code == 400

    def test_duplicate_username_returns_400(self, client):
        client.post("/v1/register", json={
            "username": "sameuser",
            "email": "first@example.com",
            "password": _TEST_PASSWORD,
            "prenom": "A",
            "nom": "B",
        })
        resp = client.post("/v1/register", json={
            "username": "sameuser",
            "email": "second@example.com",
            "password": _TEST_PASSWORD,
            "prenom": "A",
            "nom": "B",
        })
        assert resp.status_code == 400

    def test_email_of_soft_deleted_account_returns_400_not_500(self, client, db_session):
        """La contrainte UNIQUE en base porte sur email/username pour toutes les lignes,
        y compris les comptes soft-deleted (RGPD, purgés après 30j) — sans ce test, une
        régression du filtre applicatif ferait remonter une IntegrityError (500) au lieu
        d'un message 400 propre."""
        client.post("/v1/register", json={
            "username": "ghost", "email": "ghost@example.com",
            "password": _TEST_PASSWORD, "prenom": "G", "nom": "H",
        })
        user = db_session.query(models.Utilisateur).filter_by(email="ghost@example.com").first()
        user.deleted_at = datetime.utcnow()
        db_session.commit()

        resp = client.post("/v1/register", json={
            "username": "ghost2", "email": "ghost@example.com",
            "password": _TEST_PASSWORD, "prenom": "G", "nom": "H",
        })
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cet email est déjà utilisé."

    def test_username_of_soft_deleted_account_returns_400_not_500(self, client, db_session):
        client.post("/v1/register", json={
            "username": "ghostuser", "email": "ghostuser@example.com",
            "password": _TEST_PASSWORD, "prenom": "G", "nom": "H",
        })
        user = db_session.query(models.Utilisateur).filter_by(username="ghostuser").first()
        user.deleted_at = datetime.utcnow()
        db_session.commit()

        resp = client.post("/v1/register", json={
            "username": "ghostuser", "email": "other@example.com",
            "password": _TEST_PASSWORD, "prenom": "G", "nom": "H",
        })
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Ce username est déjà utilisé."


class TestLogin:
    def test_valid_credentials_return_token(self, client, registered_user):
        resp = client.post("/v1/login", json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_wrong_password_returns_403(self, client, registered_user):
        resp = client.post("/v1/login", json={
            "email": registered_user["email"],
            "password": "wrong_password",
        })
        assert resp.status_code == 403

    def test_unknown_email_returns_403(self, client):
        resp = client.post("/v1/login", json={
            "email": "nobody@example.com",
            "password": _TEST_PASSWORD,
        })
        assert resp.status_code == 403


class TestMe:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/v1/me").status_code == 401

    def test_returns_own_profile(self, auth_client, registered_user):
        resp = auth_client.get("/v1/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == registered_user["email"]
        assert data["username"] == registered_user["username"]
        assert "password_hash" not in data

    def test_update_username(self, auth_client):
        resp = auth_client.put("/v1/me", json={"username": "new_username"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "new_username"

    def test_update_with_empty_username_returns_400(self, auth_client):
        resp = auth_client.put("/v1/me", json={"username": ""})
        assert resp.status_code == 400


class TestLogout:
    def test_clears_cookie(self, client):
        resp = client.post("/v1/logout")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Déconnecté"


class TestSessions:
    def test_create_session_requires_auth(self, client):
        resp = client.post("/v1/sessions", params={"user_id": 1}, json={"title": "Test"})
        assert resp.status_code == 401

    def test_create_and_list_session(self, auth_client):
        me = auth_client.get("/v1/me").json()
        user_id = me["id"]

        create_resp = auth_client.post(
            "/v1/sessions",
            params={"user_id": user_id},
            json={"title": "Ma session"},
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["title"] == "Ma session"

        list_resp = auth_client.get("/v1/sessions", params={"user_id": user_id})
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    def test_cannot_access_other_users_sessions(self, client, mark_verified):
        # Create two users
        client.post("/v1/register", json={
            "username": "user_a", "email": "a@example.com",
            "password": _TEST_PASSWORD, "prenom": "A", "nom": "A",
        })
        client.post("/v1/register", json={
            "username": "user_b", "email": "b@example.com",
            "password": _TEST_PASSWORD, "prenom": "B", "nom": "B",
        })
        mark_verified("a@example.com")
        mark_verified("b@example.com")
        token_a = client.post("/v1/login", json={"email": "a@example.com", "password": _TEST_PASSWORD}).json()["access_token"]
        user_b_id = client.post("/v1/login", json={"email": "b@example.com", "password": _TEST_PASSWORD}).json()["user_id"]

        resp = client.get(
            "/v1/sessions",
            params={"user_id": user_b_id},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 403
