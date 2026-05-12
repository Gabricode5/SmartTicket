"""Integration tests for FastAPI endpoints."""


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
            "password": "password123",
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
            "password": "password123",
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
            "password": "password123",
            "prenom": "A",
            "nom": "B",
        })
        resp = client.post("/v1/register", json={
            "username": "sameuser",
            "email": "second@example.com",
            "password": "password123",
            "prenom": "A",
            "nom": "B",
        })
        assert resp.status_code == 400


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
            "password": "password123",
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

    def test_cannot_access_other_users_sessions(self, client):
        # Create two users
        client.post("/v1/register", json={
            "username": "user_a", "email": "a@example.com",
            "password": "pass123", "prenom": "A", "nom": "A",
        })
        client.post("/v1/register", json={
            "username": "user_b", "email": "b@example.com",
            "password": "pass123", "prenom": "B", "nom": "B",
        })
        token_a = client.post("/v1/login", json={"email": "a@example.com", "password": "pass123"}).json()["access_token"]
        user_b_id = client.post("/v1/login", json={"email": "b@example.com", "password": "pass123"}).json()["user_id"]

        resp = client.get(
            "/v1/sessions",
            params={"user_id": user_b_id},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 403
