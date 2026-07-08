"""Tests des notifications in-app : réponse SAV et ticket transféré.

Note : `client` et `auth_client` sont le même objet `TestClient` (voir conftest.py,
`auth_client` ne fait que muter les headers par défaut de `client`) — on utilise donc
des headers explicites par requête pour chaque acteur plutôt que de compter sur l'état
mutable partagé, pour éviter qu'un acteur n'écrase le jeton d'un autre en cours de test.
"""
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
            "username": "notif_admin", "email": "notif_admin@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "notif_admin@example.com", "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client, token: str, user_id: int) -> int:
    resp = client.post("/v1/sessions", params={"user_id": user_id}, json={"title": "Souci de connexion"}, headers=_auth(token))
    assert resp.status_code == 200, resp.json()
    return resp.json()["id"]


class TestSavReplyNotification:
    def test_sav_reply_notifies_the_ticket_owner(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "owner_a@example.com", "owner_a")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_session(client, owner_token, owner_id)

        admin_token = _make_admin_token(client)
        resp = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "sav", "contenu": "Bonjour, je regarde votre souci.",
        }, headers=_auth(admin_token))
        assert resp.status_code == 201

        count = client.get("/v1/notifications/unread-count", headers=_auth(owner_token)).json()["count"]
        assert count == 1

        notifications = client.get("/v1/notifications", headers=_auth(owner_token)).json()
        assert len(notifications) == 1
        assert notifications[0]["type"] == "sav_reply"
        assert notifications[0]["id_session"] == session_id
        assert notifications[0]["read"] is False

    def test_own_message_does_not_notify_self(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "owner_b@example.com", "owner_b")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_session(client, owner_token, owner_id)

        resp = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "user", "contenu": "Bonjour",
        }, headers=_auth(owner_token))
        assert resp.status_code == 201
        assert client.get("/v1/notifications/unread-count", headers=_auth(owner_token)).json()["count"] == 0

    def test_ai_message_does_not_create_notification(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "owner_c@example.com", "owner_c")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_session(client, owner_token, owner_id)

        resp = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "ai", "contenu": "Réponse générée par l'IA.",
        }, headers=_auth(owner_token))
        assert resp.status_code == 201
        assert client.get("/v1/notifications/unread-count", headers=_auth(owner_token)).json()["count"] == 0


class TestTransferNotification:
    def test_transfer_notifies_agents_not_the_transferring_user(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "owner_d@example.com", "owner_d")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_session(client, owner_token, owner_id)

        admin_token = _make_admin_token(client)
        # Un second compte "user" simple ne doit recevoir aucune notification de transfert.
        bystander_token = _register_and_get_token(client, mark_verified, "bystander@example.com", "bystander")

        resp = client.post(f"/v1/sessions/{session_id}/transfer", json={"reason": "technique"}, headers=_auth(owner_token))
        assert resp.status_code == 200, resp.json()

        assert client.get("/v1/notifications/unread-count", headers=_auth(admin_token)).json()["count"] == 1
        admin_notifications = client.get("/v1/notifications", headers=_auth(admin_token)).json()
        assert admin_notifications[0]["type"] == "session_transferred"
        assert admin_notifications[0]["id_session"] == session_id

        # L'utilisateur qui a transféré son propre ticket n'a pas à en être notifié.
        assert client.get("/v1/notifications/unread-count", headers=_auth(owner_token)).json()["count"] == 0
        assert client.get("/v1/notifications/unread-count", headers=_auth(bystander_token)).json()["count"] == 0


class TestNotificationManagement:
    def test_mark_single_notification_as_read(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "owner_e@example.com", "owner_e")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_session(client, owner_token, owner_id)
        admin_token = _make_admin_token(client)
        client.post("/v1/messages", json={"id_session": session_id, "type_envoyeur": "sav", "contenu": "Salut"}, headers=_auth(admin_token))

        notification_id = client.get("/v1/notifications", headers=_auth(owner_token)).json()[0]["id"]
        resp = client.patch(f"/v1/notifications/{notification_id}/read", headers=_auth(owner_token))
        assert resp.status_code == 200
        assert resp.json()["read"] is True
        assert client.get("/v1/notifications/unread-count", headers=_auth(owner_token)).json()["count"] == 0

    def test_mark_all_as_read(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "owner_f@example.com", "owner_f")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_session(client, owner_token, owner_id)
        admin_token = _make_admin_token(client)
        client.post("/v1/messages", json={"id_session": session_id, "type_envoyeur": "sav", "contenu": "Un"}, headers=_auth(admin_token))
        client.post("/v1/messages", json={"id_session": session_id, "type_envoyeur": "sav", "contenu": "Deux"}, headers=_auth(admin_token))

        assert client.get("/v1/notifications/unread-count", headers=_auth(owner_token)).json()["count"] == 2
        resp = client.post("/v1/notifications/read-all", headers=_auth(owner_token))
        assert resp.status_code == 200
        assert client.get("/v1/notifications/unread-count", headers=_auth(owner_token)).json()["count"] == 0
        assert all(n["read"] for n in client.get("/v1/notifications", headers=_auth(owner_token)).json())

    def test_cannot_mark_another_users_notification_as_read(self, client, mark_verified):
        owner_token = _register_and_get_token(client, mark_verified, "owner_g@example.com", "owner_g")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_session(client, owner_token, owner_id)
        admin_token = _make_admin_token(client)
        client.post("/v1/messages", json={"id_session": session_id, "type_envoyeur": "sav", "contenu": "Salut"}, headers=_auth(admin_token))
        notification_id = client.get("/v1/notifications", headers=_auth(owner_token)).json()[0]["id"]

        intruder_token = _register_and_get_token(client, mark_verified, "intruder@example.com", "intruder")
        resp = client.patch(f"/v1/notifications/{notification_id}/read", headers=_auth(intruder_token))
        assert resp.status_code == 404

    def test_requires_auth(self, client):
        assert client.get("/v1/notifications").status_code == 401
        assert client.get("/v1/notifications/unread-count").status_code == 401
