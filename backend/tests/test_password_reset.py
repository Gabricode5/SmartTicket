"""Tests de la réinitialisation de mot de passe (mot de passe oublié)."""
import secrets

from dependencies import create_password_reset_token

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _register(client, email: str, username: str):
    return client.post("/v1/register", json={
        "username": username, "email": email, "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })


class TestForgotPassword:
    def test_forgot_password_for_existing_account_returns_generic_message(self, client):
        _register(client, "forgot@example.com", "forgot_user")
        resp = client.post("/v1/forgot-password", json={"email": "forgot@example.com"})
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_forgot_password_for_unknown_email_returns_same_generic_message(self, client):
        _register(client, "known@example.com", "known_user")
        known = client.post("/v1/forgot-password", json={"email": "known@example.com"})
        unknown = client.post("/v1/forgot-password", json={"email": "doesnotexist@example.com"})
        assert known.status_code == 200
        assert unknown.status_code == 200
        assert known.json() == unknown.json()


class TestResetPassword:
    def test_reset_password_with_valid_token_allows_login_with_new_password(self, client, mark_verified):
        register_resp = _register(client, "reset@example.com", "reset_user")
        mark_verified("reset@example.com")
        user_id = register_resp.json()["id"]
        token = create_password_reset_token(user_id, "reset@example.com")

        resp = client.post("/v1/reset-password", json={"token": token, "new_password": "brand-new-password-123"})
        assert resp.status_code == 200

        old_login = client.post("/v1/login", json={"email": "reset@example.com", "password": _TEST_PASSWORD})
        assert old_login.status_code == 403

        new_login = client.post("/v1/login", json={"email": "reset@example.com", "password": "brand-new-password-123"})
        assert new_login.status_code == 200

    def test_reset_password_rejects_short_password(self, client):
        register_resp = _register(client, "shortpw@example.com", "shortpw_user")
        token = create_password_reset_token(register_resp.json()["id"], "shortpw@example.com")

        resp = client.post("/v1/reset-password", json={"token": token, "new_password": "abc"})
        assert resp.status_code == 400

    def test_reset_password_garbage_token_returns_400(self, client):
        resp = client.post("/v1/reset-password", json={"token": "not-a-real-jwt", "new_password": "whatever123"})
        assert resp.status_code == 400

    def test_email_verification_token_cannot_be_used_to_reset_password(self, client):
        from dependencies import create_email_verification_token

        register_resp = _register(client, "crosstoken@example.com", "crosstoken_user")
        verify_token = create_email_verification_token(register_resp.json()["id"], "crosstoken@example.com")

        resp = client.post("/v1/reset-password", json={"token": verify_token, "new_password": "whatever123"})
        assert resp.status_code == 400

    def test_reset_password_unknown_user_id_returns_404(self, client):
        token = create_password_reset_token(999999, "ghost@example.com")
        resp = client.post("/v1/reset-password", json={"token": token, "new_password": "whatever123"})
        assert resp.status_code == 404
