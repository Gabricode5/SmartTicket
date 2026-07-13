"""Tests de POST /v1/sessions/{id}/resolve : qui peut rendre la main à l'IA après
un transfert, et à quel moment (le client ne peut le faire qu'une fois qu'un agent
SAV a effectivement répondu, pour ne pas court-circuiter la file d'attente)."""
import os
import secrets

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _register_and_get_token(client, mark_verified, email: str, username: str) -> str:
    client.post("/v1/register", json={
        "username": username, "email": email, "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })
    mark_verified(email)
    resp = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _make_admin_token(client) -> str:
    client.post(
        "/v1/setup-admin",
        json={
            "username": "resolve_admin", "email": "resolve_admin@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "resolve_admin@example.com", "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_transferred_session(client, owner_token: str, owner_id: int) -> int:
    session_id = client.post(
        "/v1/sessions", params={"user_id": owner_id}, json={"title": "Souci de connexion"}, headers=_auth(owner_token)
    ).json()["id"]
    resp = client.post(f"/v1/sessions/{session_id}/transfer", json={"reason": "technique"}, headers=_auth(owner_token))
    assert resp.status_code == 200, resp.json()
    return session_id


class TestResolveSession:
    def test_owner_cannot_resolve_before_sav_reply(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "resolve_owner_a@example.com", "resolve_owner_a")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)

        resp = client.post(f"/v1/sessions/{session_id}/resolve", headers=_auth(owner_token))
        assert resp.status_code == 400
        assert "attente" in resp.json()["detail"].lower()

    def test_owner_can_resolve_after_sav_reply(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "resolve_owner_b@example.com", "resolve_owner_b")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)

        admin_token = _make_admin_token(client)
        client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "sav", "contenu": "Voici la solution.",
        }, headers=_auth(admin_token))

        resp = client.post(f"/v1/sessions/{session_id}/resolve", headers=_auth(owner_token))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["status"] == "open"
        assert resp.json()["transfer_reason"] is None

    def test_sav_can_resolve_even_without_replying_first(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "resolve_owner_c@example.com", "resolve_owner_c")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)

        admin_token = _make_admin_token(client)
        resp = client.post(f"/v1/sessions/{session_id}/resolve", headers=_auth(admin_token))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["status"] == "open"

    def test_bystander_cannot_resolve_someone_elses_session(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "resolve_owner_d@example.com", "resolve_owner_d")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)

        bystander_token = _register_and_get_token(client, mark_verified, "resolve_bystander@example.com", "resolve_bystander")
        resp = client.post(f"/v1/sessions/{session_id}/resolve", headers=_auth(bystander_token))
        assert resp.status_code == 403

    def test_cannot_resolve_a_session_that_is_not_transferred(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "resolve_owner_e@example.com", "resolve_owner_e")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = client.post(
            "/v1/sessions", params={"user_id": owner_id}, json={"title": "Session ouverte"}, headers=_auth(owner_token)
        ).json()["id"]

        resp = client.post(f"/v1/sessions/{session_id}/resolve", headers=_auth(owner_token))
        assert resp.status_code == 400

    def test_requires_auth(self, client):
        resp = client.post("/v1/sessions/1/resolve")
        assert resp.status_code == 401
