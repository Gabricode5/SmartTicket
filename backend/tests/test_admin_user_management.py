"""Tests de PUT /v1/users/{id} (update_user_by_admin) : protection RGPD des données
personnelles d'un utilisateur final (2026-08-19) — un admin peut voir un client, changer son
rôle et supprimer son compte, mais jamais réécrire prénom/nom/email/username à sa place. Un
membre de l'équipe (sav/superviseur/admin) reste éditable en entier."""
import os
import secrets

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _register_and_login(client, email: str, username: str, mark_verified):
    client.post("/v1/register", json={
        "username": username, "email": email, "password": _TEST_PASSWORD, "prenom": "Pat", "nom": "Original",
    })
    mark_verified(email)
    resp = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"], resp.json()["user_id"]


def _make_admin_client(client):
    client.post(
        "/v1/setup-admin",
        json={
            "username": "admin_pii_test", "email": "admin_pii_test@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "admin_pii_test@example.com", "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    client.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
    return client


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAdminCannotEditEndUserIdentity:
    def test_admin_cannot_change_end_user_email(self, client, mark_verified):
        _, target_id = _register_and_login(client, "enduser_a@example.com", "enduser_a", mark_verified)
        admin_client = _make_admin_client(client)

        resp = admin_client.put(f"/v1/users/{target_id}", json={"email": "hijacked@example.com"})
        assert resp.status_code == 403, resp.json()
        assert "rgpd" in resp.json()["detail"].lower() or "personnelles" in resp.json()["detail"].lower()

    def test_admin_cannot_change_end_user_username(self, client, mark_verified):
        _, target_id = _register_and_login(client, "enduser_b@example.com", "enduser_b", mark_verified)
        admin_client = _make_admin_client(client)

        resp = admin_client.put(f"/v1/users/{target_id}", json={"username": "renamed_by_admin"})
        assert resp.status_code == 403, resp.json()

    def test_admin_cannot_change_end_user_first_or_last_name(self, client, mark_verified):
        _, target_id = _register_and_login(client, "enduser_c@example.com", "enduser_c", mark_verified)
        admin_client = _make_admin_client(client)

        resp = admin_client.put(f"/v1/users/{target_id}", json={"prenom": "Autre", "nom": "Personne"})
        assert resp.status_code == 403, resp.json()

    def test_identity_fields_rejected_even_when_bundled_with_a_role_change(self, client, mark_verified):
        """Tout ou rien : un admin ne peut pas se glisser un changement d'email en même temps
        qu'un changement de rôle légitime -- la requête entière est refusée, rien n'est
        appliqué partiellement."""
        _, target_id = _register_and_login(client, "enduser_d@example.com", "enduser_d", mark_verified)
        admin_client = _make_admin_client(client)

        resp = admin_client.put(f"/v1/users/{target_id}", json={"role": "sav", "email": "hijacked2@example.com"})
        assert resp.status_code == 403, resp.json()

        # Confirme qu'AUCUN champ n'a été appliqué (ni le rôle, ni l'email).
        listing = admin_client.get("/v1/users", params={"role": "user"}).json()
        target = next(u for u in listing if u["id"] == target_id)
        assert target["email"] == "enduser_d@example.com"

    def test_admin_can_still_change_end_user_role_alone(self, client, mark_verified):
        _, target_id = _register_and_login(client, "enduser_e@example.com", "enduser_e", mark_verified)
        admin_client = _make_admin_client(client)

        resp = admin_client.put(f"/v1/users/{target_id}", json={"role": "sav"})
        assert resp.status_code == 200, resp.json()
        assert resp.json()["role"] == "sav"

    def test_admin_can_still_delete_an_end_user(self, client, mark_verified):
        """Droit à l'effacement : la suppression reste permise, seule l'ALTÉRATION des
        données personnelles est bloquée."""
        _, target_id = _register_and_login(client, "enduser_f@example.com", "enduser_f", mark_verified)
        admin_client = _make_admin_client(client)

        resp = admin_client.delete(f"/v1/users/{target_id}")
        assert resp.status_code == 204, resp.text


class TestAdminCanEditTeamMemberIdentity:
    def test_admin_can_change_a_sav_agents_identity_fields(self, client, mark_verified):
        _, target_id = _register_and_login(client, "agent_g@example.com", "agent_g", mark_verified)
        admin_client = _make_admin_client(client)
        promote = admin_client.put(f"/v1/users/{target_id}/role", json={"role": "sav"})
        assert promote.status_code == 200

        resp = admin_client.put(f"/v1/users/{target_id}", json={
            "username": "agent_g_renamed", "email": "agent_g_new@example.com", "prenom": "Nouveau", "nom": "Nom",
        })
        assert resp.status_code == 200, resp.json()
        assert resp.json()["username"] == "agent_g_renamed"
        assert resp.json()["email"] == "agent_g_new@example.com"
        assert resp.json()["prenom"] == "Nouveau"


class TestSelfServiceUnaffected:
    def test_user_can_still_update_their_own_profile_via_me(self, client, mark_verified):
        token, _ = _register_and_login(client, "selfservice_h@example.com", "selfservice_h", mark_verified)

        resp = client.put("/v1/me", json={"prenom": "Modifié"}, headers=_auth(token))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["prenom"] == "Modifié"


class TestAuth:
    def test_regular_user_cannot_call_admin_edit_endpoint(self, client, mark_verified):
        token, target_id = _register_and_login(client, "bystander_i@example.com", "bystander_i", mark_verified)
        resp = client.put(f"/v1/users/{target_id}", json={"role": "sav"}, headers=_auth(token))
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        resp = client.put("/v1/users/1", json={"role": "sav"})
        assert resp.status_code == 401
