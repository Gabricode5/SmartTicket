"""Tests de la vérification d'email à l'inscription."""
import secrets

from dependencies import create_email_verification_token

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _register(client, email: str, username: str):
    return client.post("/v1/register", json={
        "username": username, "email": email, "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })


class TestRegistration:
    def test_new_user_is_not_verified(self, client):
        resp = _register(client, "unverified@example.com", "unverified_user")
        assert resp.status_code == 201
        assert resp.json()["email_verified"] is False


class TestLoginBlockedUntilVerified:
    def test_login_rejected_before_verification(self, client):
        _register(client, "pending@example.com", "pending_user")
        resp = client.post("/v1/login", json={"email": "pending@example.com", "password": _TEST_PASSWORD})
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "email_not_verified"

    def test_login_succeeds_after_verification(self, client):
        register_resp = _register(client, "verifyme@example.com", "verifyme_user")
        user_id = register_resp.json()["id"]
        token = create_email_verification_token(user_id, "verifyme@example.com")

        verify_resp = client.get("/v1/verify-email", params={"token": token})
        assert verify_resp.status_code == 200

        login_resp = client.post("/v1/login", json={"email": "verifyme@example.com", "password": _TEST_PASSWORD})
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()


class TestVerifyEmailEndpoint:
    def test_verifying_twice_is_idempotent(self, client):
        register_resp = _register(client, "twice@example.com", "twice_user")
        token = create_email_verification_token(register_resp.json()["id"], "twice@example.com")

        first = client.get("/v1/verify-email", params={"token": token})
        second = client.get("/v1/verify-email", params={"token": token})
        assert first.status_code == 200
        assert second.status_code == 200

    def test_garbage_token_returns_400(self, client):
        resp = client.get("/v1/verify-email", params={"token": "not-a-real-jwt"})
        assert resp.status_code == 400

    def test_access_token_cannot_be_used_as_verification_token(self, client, registered_user, auth_client):
        # auth_client's cookie/header already carries a real access token — it must be
        # rejected here since it lacks the `type: email_verification` claim.
        access_token = auth_client.headers["Authorization"].removeprefix("Bearer ").strip()
        resp = auth_client.get("/v1/verify-email", params={"token": access_token})
        assert resp.status_code == 400

    def test_unknown_user_id_returns_404(self, client):
        token = create_email_verification_token(999999, "ghost@example.com")
        resp = client.get("/v1/verify-email", params={"token": token})
        assert resp.status_code == 404


class TestResendVerification:
    def test_resend_for_unverified_account_returns_generic_message(self, client):
        _register(client, "resend@example.com", "resend_user")
        resp = client.post("/v1/resend-verification", json={"email": "resend@example.com"})
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_resend_for_unknown_email_returns_same_generic_message(self, client):
        known = client.post("/v1/resend-verification", json={"email": "doesnotexist@example.com"})
        assert known.status_code == 200
        assert "message" in known.json()

    def test_resend_does_not_leak_whether_account_exists(self, client):
        _register(client, "exists@example.com", "exists_user")
        existing = client.post("/v1/resend-verification", json={"email": "exists@example.com"})
        missing = client.post("/v1/resend-verification", json={"email": "doesnotexist2@example.com"})
        assert existing.json() == missing.json()

    def test_resend_after_verification_still_returns_generic_message(self, client, mark_verified):
        _register(client, "alreadyverified@example.com", "alreadyverified_user")
        mark_verified("alreadyverified@example.com")
        resp = client.post("/v1/resend-verification", json={"email": "alreadyverified@example.com"})
        assert resp.status_code == 200


class TestEmailChangeResetsVerification:
    def test_changing_email_requires_reverification(self, client, registered_user, auth_client):
        resp = auth_client.put("/v1/me", json={"email": "new-address@example.com"})
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is False

        login_resp = client.post("/v1/login", json={
            "email": "new-address@example.com", "password": registered_user["password"],
        })
        assert login_resp.status_code == 403

    def test_keeping_same_email_does_not_reset_verification(self, client, registered_user, auth_client):
        resp = auth_client.put("/v1/me", json={"email": registered_user["email"]})
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is True


class TestSetupAdminIsAutoVerified:
    def test_setup_admin_account_is_verified(self, client):
        import os
        client.post(
            "/v1/setup-admin",
            json={
                "username": "auto_admin", "email": "auto_admin@example.com",
                "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
            },
            headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
        )
        login_resp = client.post("/v1/login", json={"email": "auto_admin@example.com", "password": _TEST_PASSWORD})
        assert login_resp.status_code == 200
