"""Tests du rôle superviseur SAV : hérite des droits agent, gère user<->sav, jamais admin."""
import os
import secrets

# Généré aléatoirement à chaque run (jamais une chaîne en dur) pour créer des comptes
# jetables dans la base de test locale/CI (conftest.py refuse de démarrer si
# TEST_DATABASE_URL ne contient pas "test" — ces comptes ne peuvent jamais exister ailleurs).
_TEST_PASSWORD = secrets.token_urlsafe(16)


def _register_and_login(client, email: str, username: str, mark_verified):
    client.post("/v1/register", json={
        "username": username, "email": email, "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })
    mark_verified(email)
    resp = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"], resp.json()["user_id"]


def _make_admin_token(client):
    # /setup-admin marque déjà email_verified=True (compte de confiance, pas d'inscription
    # publique) — pas besoin de mark_verified ici.
    client.post(
        "/v1/setup-admin",
        json={
            "username": "sup_test_admin", "email": "sup_admin@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "sup_admin@example.com", "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _make_supervisor_client(client, mark_verified):
    """Crée un utilisateur, le promeut superviseur via un admin temporaire, et
    authentifie `client` en tant que ce superviseur."""
    supervisor_token, supervisor_id = _register_and_login(client, "sup_agent@example.com", "sup_agent", mark_verified)
    admin_token = _make_admin_token(client)

    promote_resp = client.put(
        f"/v1/users/{supervisor_id}/role",
        json={"role": "superviseur"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert promote_resp.status_code == 200, promote_resp.json()
    assert promote_resp.json()["role"] == "superviseur"

    client.headers.update({"Authorization": f"Bearer {supervisor_token}"})
    return client, supervisor_id


class TestSupervisorTeamManagement:
    def test_supervisor_can_list_users(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        resp = supervisor_client.get("/v1/users", params={"role": "user"})
        assert resp.status_code == 200

    def test_supervisor_can_promote_user_to_sav(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        _, agent_id = _register_and_login(client, "future_agent@example.com", "future_agent", mark_verified)

        resp = supervisor_client.put(f"/v1/users/{agent_id}/role", json={"role": "sav"})
        assert resp.status_code == 200, resp.json()
        assert resp.json()["role"] == "sav"

    def test_supervisor_can_demote_sav_to_user(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        _, agent_id = _register_and_login(client, "future_agent2@example.com", "future_agent2", mark_verified)

        promote = supervisor_client.put(f"/v1/users/{agent_id}/role", json={"role": "sav"})
        assert promote.status_code == 200

        demote = supervisor_client.put(f"/v1/users/{agent_id}/role", json={"role": "user"})
        assert demote.status_code == 200, demote.json()
        assert demote.json()["role"] == "user"

    def test_supervisor_cannot_promote_to_admin(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        _, target_id = _register_and_login(client, "wannabe_admin@example.com", "wannabe_admin", mark_verified)

        resp = supervisor_client.put(f"/v1/users/{target_id}/role", json={"role": "admin"})
        assert resp.status_code == 403

    def test_supervisor_cannot_modify_admin_account(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        admin_row = supervisor_client.get("/v1/users", params={"role": "admin"}).json()
        admin_id = admin_row[0]["id"]

        resp = supervisor_client.put(f"/v1/users/{admin_id}/role", json={"role": "sav"})
        assert resp.status_code == 403

    def test_supervisor_cannot_delete_users(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        _, target_id = _register_and_login(client, "todelete@example.com", "todelete", mark_verified)

        resp = supervisor_client.delete(f"/v1/users/{target_id}")
        assert resp.status_code == 403

    def test_supervisor_cannot_edit_user_profile(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        _, target_id = _register_and_login(client, "toedit@example.com", "toedit", mark_verified)

        resp = supervisor_client.put(f"/v1/users/{target_id}", json={"username": "renamed"})
        assert resp.status_code == 403


class TestSupervisorAgentAccess:
    """Un superviseur doit avoir accès à tout ce qu'un agent SAV a déjà."""

    def test_supervisor_can_access_transferred_sessions(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        resp = supervisor_client.get("/v1/sessions/transferred")
        assert resp.status_code == 200

    def test_supervisor_can_access_analytics_stats(self, client, mark_verified):
        supervisor_client, _ = _make_supervisor_client(client, mark_verified)
        resp = supervisor_client.get("/v1/analytics/stats")
        assert resp.status_code == 200
