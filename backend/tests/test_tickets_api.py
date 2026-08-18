"""Tests de l'Étape 2 du chantier ticketing SAV : création automatique du ticket au
transfert, endpoints de liste/recherche/détail/transitions/assignation, et le flip
waiting_on="customer" sur une réponse SAV via l'endpoint /v1/messages existant."""
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
            "username": "tix_admin", "email": "tix_admin@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "tix_admin@example.com", "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _promote(client, admin_token: str, user_id: int, role: str) -> None:
    resp = client.put(f"/v1/users/{user_id}/role", json={"role": role}, headers=_auth(admin_token))
    assert resp.status_code == 200, resp.json()


def _make_agent(client, mark_verified, admin_token: str, email: str, username: str) -> tuple[str, int]:
    token = _register_and_get_token(client, mark_verified, email, username)
    user_id = client.get("/v1/me", headers=_auth(token)).json()["id"]
    _promote(client, admin_token, user_id, "sav")
    return token, user_id


def _make_supervisor(client, mark_verified, admin_token: str, email: str, username: str) -> tuple[str, int]:
    token = _register_and_get_token(client, mark_verified, email, username)
    user_id = client.get("/v1/me", headers=_auth(token)).json()["id"]
    _promote(client, admin_token, user_id, "superviseur")
    return token, user_id


def _create_transferred_session(client, owner_token: str, owner_id: int, *, reason: str = "technique") -> int:
    session_id = client.post(
        "/v1/sessions", params={"user_id": owner_id}, json={"title": "Souci de connexion"}, headers=_auth(owner_token)
    ).json()["id"]
    resp = client.post(f"/v1/sessions/{session_id}/transfer", json={"reason": reason}, headers=_auth(owner_token))
    assert resp.status_code == 200, resp.json()
    return session_id


class TestTicketAutoCreationOnTransfer:
    def test_transfer_creates_a_ticket_with_expected_defaults(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_a@example.com", "tix_owner_a")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id, reason="sensible")

        resp = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token))
        assert resp.status_code == 200, resp.json()
        matching = [t for t in resp.json()["items"] if t["session_id"] == session_id]
        assert len(matching) == 1
        ticket = matching[0]
        assert ticket["status"] == "new"
        assert ticket["waiting_on"] == "us"
        assert ticket["assigned_agent_id"] is None
        assert ticket["priority"] == "normal"
        assert ticket["reason"] == "sensible"
        assert ticket["client_username"] == "tix_owner_a"
        assert ticket["ticket_number"] >= 1000

    def test_reason_survives_after_the_session_resolves(self, client, mark_verified):
        """Root cause de la lacune n°1 (Étape 0) : session.transfer_reason est effacé par
        resolve_session(). Ticket.reason est un snapshot, il ne doit PAS suivre."""
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_b@example.com", "tix_owner_b")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id, reason="complexe")
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][0]["id"]

        resolve_resp = client.post(f"/v1/sessions/{session_id}/resolve", headers=_auth(admin_token))
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["transfer_reason"] is None  # confirme que la source EST bien effacée

        ticket_resp = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(admin_token))
        assert ticket_resp.status_code == 200
        assert ticket_resp.json()["reason"] == "complexe"  # le snapshot survit

    def test_context_cutoff_excludes_the_transfer_system_message(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_c@example.com", "tix_owner_c")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = client.post(
            "/v1/sessions", params={"user_id": owner_id}, json={"title": "T"}, headers=_auth(owner_token)
        ).json()["id"]
        client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "user", "contenu": "Bonjour, j'ai un souci.",
        }, headers=_auth(owner_token))
        last_message_before_transfer = client.get(
            "/v1/messages", params={"session_id": session_id}, headers=_auth(owner_token)
        ).json()[-1]["id"]

        resp = client.post(f"/v1/sessions/{session_id}/transfer", json={"reason": "technique"}, headers=_auth(owner_token))
        assert resp.status_code == 200

        ticket = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][0]
        assert ticket["context_cutoff_message_id"] == last_message_before_transfer

    def test_second_transfer_cycle_on_same_session_creates_a_new_ticket(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_d@example.com", "tix_owner_d")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)
        first_ticket = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][0]

        client.post(f"/v1/sessions/{session_id}/resolve", headers=_auth(admin_token))
        resp = client.post(f"/v1/sessions/{session_id}/transfer", json={"reason": "autre"}, headers=_auth(owner_token))
        assert resp.status_code == 200

        tickets = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"]
        session_tickets = [t for t in tickets if t["session_id"] == session_id]
        assert len(session_tickets) == 2
        ticket_numbers = {t["ticket_number"] for t in session_tickets}
        assert len(ticket_numbers) == 2
        assert first_ticket["ticket_number"] in ticket_numbers


class TestTicketListAndSearch:
    def test_filters_by_status_and_waiting_on(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_e@example.com", "tix_owner_e")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][0]["id"]
        client.patch(f"/v1/tickets/{ticket_id}/status", json={"status": "in_progress"}, headers=_auth(admin_token))

        resp = client.get("/v1/tickets", params={"status": "in_progress"}, headers=_auth(admin_token))
        assert resp.status_code == 200
        assert any(t["id"] == ticket_id for t in resp.json()["items"])

        resp_no_match = client.get("/v1/tickets", params={"status": "closed"}, headers=_auth(admin_token))
        assert not any(t["id"] == ticket_id for t in resp_no_match.json()["items"])

    def test_rejects_invalid_status_filter(self, client):
        admin_token = _make_admin_token(client)
        resp = client.get("/v1/tickets", params={"status": "bogus"}, headers=_auth(admin_token))
        assert resp.status_code == 400

    def test_search_by_ticket_number(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_f@example.com", "tix_owner_f")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]

        resp = client.get("/v1/tickets/search", params={"q": str(ticket["ticket_number"])}, headers=_auth(admin_token))
        assert resp.status_code == 200
        assert [t["id"] for t in resp.json()["items"]] == [ticket["id"]]

    def test_search_by_client_email(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_g@example.com", "tix_owner_g")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)

        resp = client.get("/v1/tickets/search", params={"q": "tix_owner_g@example.com"}, headers=_auth(admin_token))
        assert resp.status_code == 200
        assert any(t["session_id"] == session_id for t in resp.json()["items"])


class TestTicketStatusAndWaitingOnTransitions:
    def test_status_and_waiting_on_are_independent(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_h@example.com", "tix_owner_h")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        resp = client.patch(f"/v1/tickets/{ticket_id}/status", json={"status": "in_progress"}, headers=_auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"
        assert resp.json()["waiting_on"] == "us"  # inchangé

        resp = client.patch(f"/v1/tickets/{ticket_id}/waiting_on", json={"waiting_on": "customer"}, headers=_auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["waiting_on"] == "customer"
        assert resp.json()["status"] == "in_progress"  # inchangé

    def test_rejects_invalid_waiting_on_value(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_i@example.com", "tix_owner_i")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        resp = client.patch(f"/v1/tickets/{ticket_id}/waiting_on", json={"waiting_on": "bogus"}, headers=_auth(admin_token))
        assert resp.status_code == 400


class TestTicketAssignmentPermissions:
    def test_agent_can_self_assign_a_free_ticket(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_j@example.com", "tix_owner_j")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent_token, agent_id = _make_agent(client, mark_verified, admin_token, "tix_agent_a@example.com", "tix_agent_a")
        resp = client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent_token))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["assigned_agent_id"] == agent_id

    def test_agent_cannot_see_or_assign_a_ticket_assigned_to_another_agent(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_k@example.com", "tix_owner_k")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent1_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_b@example.com", "tix_agent_b")
        client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent1_token))

        agent2_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_c@example.com", "tix_agent_c")
        # Cloisonnement strict : même en lecture, un sav ne voit pas le ticket d'un autre agent.
        get_resp = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(agent2_token))
        assert get_resp.status_code == 404
        assign_resp = client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent2_token))
        assert assign_resp.status_code == 404

    def test_agent_not_in_list_when_ticket_assigned_to_someone_else(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_l@example.com", "tix_owner_l")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent1_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_d@example.com", "tix_agent_d")
        client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent1_token))

        agent2_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_e@example.com", "tix_agent_e")
        listing = client.get("/v1/tickets", headers=_auth(agent2_token)).json()["items"]
        assert ticket_id not in [t["id"] for t in listing]

    def test_supervisor_can_assign_ticket_to_any_agent(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_m@example.com", "tix_owner_m")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent_token, agent_id = _make_agent(client, mark_verified, admin_token, "tix_agent_f@example.com", "tix_agent_f")
        supervisor_token, _ = _make_supervisor(client, mark_verified, admin_token, "tix_super_a@example.com", "tix_super_a")

        resp = client.post(f"/v1/tickets/{ticket_id}/assign", json={"agent_id": agent_id}, headers=_auth(supervisor_token))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["assigned_agent_id"] == agent_id

    def test_supervisor_can_reassign_an_already_assigned_ticket(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_n@example.com", "tix_owner_n")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent1_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_g@example.com", "tix_agent_g")
        client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent1_token))
        _, agent2_id = _make_agent(client, mark_verified, admin_token, "tix_agent_h@example.com", "tix_agent_h")
        supervisor_token, _ = _make_supervisor(client, mark_verified, admin_token, "tix_super_b@example.com", "tix_super_b")

        resp = client.post(f"/v1/tickets/{ticket_id}/assign", json={"agent_id": agent2_id}, headers=_auth(supervisor_token))
        assert resp.status_code == 200, resp.json()
        assert resp.json()["assigned_agent_id"] == agent2_id

    def test_supervisor_sees_tickets_assigned_to_any_agent(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_o@example.com", "tix_owner_o")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_i@example.com", "tix_agent_i")
        client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent_token))
        supervisor_token, _ = _make_supervisor(client, mark_verified, admin_token, "tix_super_c@example.com", "tix_super_c")

        resp = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(supervisor_token))
        assert resp.status_code == 200


class TestReplyFlipsWaitingOn:
    def test_sav_reply_flips_waiting_on_to_customer(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_p@example.com", "tix_owner_p")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        reply = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "sav", "contenu": "Je regarde ça tout de suite.",
        }, headers=_auth(admin_token))
        assert reply.status_code == 201, reply.json()

        ticket = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(admin_token)).json()
        assert ticket["waiting_on"] == "customer"

    def test_user_reply_does_not_flip_waiting_on(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_q@example.com", "tix_owner_q")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "user", "contenu": "Toujours pas de nouvelles ?",
        }, headers=_auth(owner_token))

        ticket = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(admin_token)).json()
        assert ticket["waiting_on"] == "us"

    def test_sav_reply_to_a_free_ticket_self_assigns_it(self, client, mark_verified):
        """Bug trouvé le 2026-08-17 : répondre à un ticket libre ne l'assignait pas -- deux
        agents pouvaient répondre au même ticket libre sans qu'aucun ne soit responsable.
        Une seule requête doit à la fois assigner ET flipper waiting_on."""
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_r@example.com", "tix_owner_r")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent_token, agent_id = _make_agent(client, mark_verified, admin_token, "tix_agent_j2@example.com", "tix_agent_j2")
        reply = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "sav", "contenu": "Je regarde ça.",
        }, headers=_auth(agent_token))
        assert reply.status_code == 201, reply.json()

        ticket = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(agent_token)).json()
        assert ticket["assigned_agent_id"] == agent_id
        assert ticket["waiting_on"] == "customer"

    def test_sav_reply_to_own_already_assigned_ticket_does_not_change_assignment(self, client, mark_verified):
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_s@example.com", "tix_owner_s")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent_token, agent_id = _make_agent(client, mark_verified, admin_token, "tix_agent_k2@example.com", "tix_agent_k2")
        client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent_token))

        reply = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "sav", "contenu": "Toujours dessus.",
        }, headers=_auth(agent_token))
        assert reply.status_code == 201, reply.json()

        ticket = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(agent_token)).json()
        assert ticket["assigned_agent_id"] == agent_id

    def test_sav_cannot_reply_to_another_agents_ticket(self, client, mark_verified):
        """POST /messages appliquait is_admin_or_sav() (accès à toute session transférée) sans
        vérifier l'assignation du ticket -- contournait le cloisonnement de GET/PATCH
        /tickets/{id}. Un agent sav ne doit pas pouvoir répondre sur le ticket d'un collègue,
        même via cet endpoint générique."""
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_t@example.com", "tix_owner_t")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        agent1_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_l2@example.com", "tix_agent_l2")
        client.post(f"/v1/tickets/{ticket_id}/assign", json={}, headers=_auth(agent1_token))

        agent2_token, _ = _make_agent(client, mark_verified, admin_token, "tix_agent_m2@example.com", "tix_agent_m2")
        reply = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "sav", "contenu": "Je prends.",
        }, headers=_auth(agent2_token))
        assert reply.status_code == 404

    def test_supervisor_reply_to_a_free_ticket_does_not_self_assign(self, client, mark_verified):
        """Décision validée le 2026-08-17 : un superviseur/admin peut dépanner un ticket libre
        sans se l'attribuer -- il garde sa vue globale, le ticket reste dans la file pour un
        agent sav. Seul le rôle sav strict s'auto-assigne."""
        admin_token = _make_admin_token(client)
        owner_token = _register_and_get_token(client, mark_verified, "tix_owner_u@example.com", "tix_owner_u")
        owner_id = client.get("/v1/me", headers=_auth(owner_token)).json()["id"]
        session_id = _create_transferred_session(client, owner_token, owner_id)
        ticket_id = client.get("/v1/tickets", params={"unassigned": True}, headers=_auth(admin_token)).json()["items"][-1]["id"]

        supervisor_token, _ = _make_supervisor(client, mark_verified, admin_token, "tix_super_d@example.com", "tix_super_d")
        reply = client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "sav", "contenu": "Je regarde en attendant qu'un agent se libère.",
        }, headers=_auth(supervisor_token))
        assert reply.status_code == 201, reply.json()

        ticket = client.get(f"/v1/tickets/{ticket_id}", headers=_auth(admin_token)).json()
        assert ticket["assigned_agent_id"] is None
        assert ticket["waiting_on"] == "customer"


class TestTicketAccessControl:
    def test_regular_user_cannot_access_tickets(self, client, mark_verified):
        token = _register_and_get_token(client, mark_verified, "tix_bystander@example.com", "tix_bystander")
        resp = client.get("/v1/tickets", headers=_auth(token))
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        resp = client.get("/v1/tickets")
        assert resp.status_code == 401
