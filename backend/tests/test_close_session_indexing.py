"""Tests de l'indexation (désactivée par défaut) du transcript d'un ticket clos dans le RAG.

INDEX_CLOSED_TICKETS=false par défaut : en B2B2C (support public), indexer le contenu d'une
conversation dans la base de connaissances partagée exposerait les futurs utilisateurs à des
fragments de conversations d'autres clients finaux.
"""
from unittest.mock import patch

import models


def _create_session_with_message(auth_client, user_id: int) -> int:
    resp = auth_client.post("/v1/sessions", params={"user_id": user_id}, json={"title": "Souci"})
    session_id = resp.json()["id"]
    auth_client.post("/v1/messages", json={
        "id_session": session_id, "type_envoyeur": "user", "contenu": "J'ai un problème avec ma commande n°12345.",
    })
    return session_id


class TestClosedTicketIndexingDisabledByDefault:
    def test_closing_a_session_does_not_create_knowledge_base_entries(self, auth_client, db_session):
        me = auth_client.get("/v1/me").json()
        session_id = _create_session_with_message(auth_client, me["id"])

        before = db_session.query(models.KnowledgeBase).count()
        resp = auth_client.post(f"/v1/sessions/{session_id}/close")
        assert resp.status_code == 200
        after = db_session.query(models.KnowledgeBase).count()

        assert after == before


class TestClosedTicketIndexingWhenEnabled:
    def test_closing_a_session_creates_knowledge_base_entries_when_flag_enabled(self, auth_client, db_session):
        me = auth_client.get("/v1/me").json()
        session_id = _create_session_with_message(auth_client, me["id"])

        with patch("routers.sessions.INDEX_CLOSED_TICKETS", True), \
             patch("routers.sessions.generate_text", return_value="Résumé du ticket."), \
             patch("routers.sessions.embed_text", return_value=[0.0] * 1024):
            resp = auth_client.post(f"/v1/sessions/{session_id}/close")

        assert resp.status_code == 200
        categories = {row.category for row in db_session.query(models.KnowledgeBase).all()}
        assert "ticket_summary" in categories
        assert "ticket_transcript" in categories
