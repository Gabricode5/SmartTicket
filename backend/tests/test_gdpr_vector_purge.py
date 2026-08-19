"""Tests du correctif RGPD bloquant #4 : les entrées knowledge_base dérivées d'un ticket clos
(INDEX_CLOSED_TICKETS, cf. routers/sessions.py::close_session) doivent être (1) purgeables par
user_id/session_id sans dépendre du texte libre `contenu`, (2) automatiquement effacées quand un
utilisateur est hard-deleted (cascade FK, sans code applicatif), et (3) non-fuyantes : le RAG ne
doit jamais servir le transcript d'un client final à un autre client final (B2B2C).
"""
import math
import os
import secrets
from unittest.mock import patch

import gdpr_purge
import models

_TEST_PASSWORD = secrets.token_urlsafe(16)
EMBED_DIM = 1024


def make_vector(seed: int = 0) -> list[float]:
    """Vecteur unitaire déterministe — même seed = même vecteur = distance cosinus 0."""
    raw = [math.sin(i * 0.1 + seed) for i in range(EMBED_DIM)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


def _make_user(db_session, *, email: str, role: str = "user") -> models.Utilisateur:
    role_row = db_session.query(models.Role).filter_by(nom_role=role).first()
    user = models.Utilisateur(
        username=email.split("@")[0], email=email, password_hash="x", id_role=role_row.id, email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_session(db_session, user: models.Utilisateur) -> models.ChatSession:
    session = models.ChatSession(id_utilisateur=user.id, status="closed")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _seed_ticket_kb_entry(db_session, *, user_id: int, session_id: int, seed: int, contenu: str) -> models.KnowledgeBase:
    row = models.KnowledgeBase(
        contenu=contenu, embedding=make_vector(seed), category="ticket_transcript",
        source_user_id=user_id, source_session_id=session_id,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_admin_client(client, mark_verified, *, email: str = "gdpr_admin@example.com"):
    client.post(
        "/v1/setup-admin",
        json={"username": "gdpr_admin", "email": email, "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test"},
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    client.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
    return client


class TestPurgeFunctions:
    def test_purge_by_user_id_removes_only_that_users_entries(self, db_session):
        user_a = _make_user(db_session, email="purge_a@example.com")
        user_b = _make_user(db_session, email="purge_b@example.com")
        session_a = _make_session(db_session, user_a)
        session_b = _make_session(db_session, user_b)
        _seed_ticket_kb_entry(db_session, user_id=user_a.id, session_id=session_a.id, seed=1, contenu="ticket de A")
        _seed_ticket_kb_entry(db_session, user_id=user_b.id, session_id=session_b.id, seed=2, contenu="ticket de B")

        deleted = gdpr_purge.purge_knowledge_base_for_user(db_session, user_a.id)
        db_session.commit()

        assert deleted == 1
        remaining = db_session.query(models.KnowledgeBase).all()
        assert len(remaining) == 1
        assert remaining[0].source_user_id == user_b.id

    def test_purge_by_session_id_removes_only_that_sessions_entries(self, db_session):
        user = _make_user(db_session, email="purge_multi_session@example.com")
        session_1 = _make_session(db_session, user)
        session_2 = _make_session(db_session, user)
        _seed_ticket_kb_entry(db_session, user_id=user.id, session_id=session_1.id, seed=3, contenu="ticket #1")
        _seed_ticket_kb_entry(db_session, user_id=user.id, session_id=session_2.id, seed=4, contenu="ticket #2")

        deleted = gdpr_purge.purge_knowledge_base_for_session(db_session, session_1.id)
        db_session.commit()

        assert deleted == 1
        remaining = db_session.query(models.KnowledgeBase).all()
        assert len(remaining) == 1
        assert remaining[0].source_session_id == session_2.id


class TestCascadeOnHardDelete:
    def test_hard_deleting_a_user_cascades_to_knowledge_base_without_calling_purge(self, db_session):
        """Preuve que ON DELETE CASCADE suffit seul -- purge_soft_deleted (main.py) n'a besoin
        d'aucun appel explicite à gdpr_purge, la base de données fait le travail."""
        user = _make_user(db_session, email="cascade_target@example.com")
        session = _make_session(db_session, user)
        _seed_ticket_kb_entry(db_session, user_id=user.id, session_id=session.id, seed=5, contenu="à effacer par cascade")

        db_session.delete(user)
        db_session.commit()

        assert db_session.query(models.KnowledgeBase).count() == 0


class TestUserDeletionEndpointPurgesImmediately:
    def test_admin_deleting_a_user_purges_their_knowledge_base_entries_immediately(self, client, mark_verified, db_session):
        """DELETE /users/{id} ne fait qu'un soft-delete (deleted_at) -- la cascade FK ne se
        déclenchera donc que 30 jours plus tard, à purge_soft_deleted. Les entrées RAG doivent
        disparaître tout de suite, pas attendre la rétention standard."""
        client.post("/v1/register", json={
            "username": "purge_target", "email": "purge_target@example.com",
            "password": _TEST_PASSWORD, "prenom": "P", "nom": "T",
        })
        mark_verified("purge_target@example.com")
        target_id = client.post("/v1/login", json={
            "email": "purge_target@example.com", "password": _TEST_PASSWORD,
        }).json()["user_id"]
        session = models.ChatSession(id_utilisateur=target_id, status="closed")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        _seed_ticket_kb_entry(db_session, user_id=target_id, session_id=session.id, seed=6, contenu="à purger immédiatement")

        admin_client = _make_admin_client(client, mark_verified)
        resp = admin_client.delete(f"/v1/users/{target_id}")
        assert resp.status_code == 204

        assert db_session.query(models.KnowledgeBase).filter(models.KnowledgeBase.source_user_id == target_id).count() == 0
        target = db_session.query(models.Utilisateur).filter(models.Utilisateur.id == target_id).first()
        assert target is not None and target.deleted_at is not None  # soft-delete seul, pas de hard-delete ici


class TestRagVisibilityFilter:
    """La colonne source_user_id qui rend la purge possible sert aussi de filtre anti-fuite :
    sans lui, activer INDEX_CLOSED_TICKETS resterait dangereux en B2B2C même avec une purge
    parfaite (une entrée reste exposée pendant toute sa durée de vie avant purge)."""

    def _ask(self, client, seed: int):
        session_id = client.post("/v1/sessions", params={"user_id": client.get("/v1/me").json()["id"]}, json={"title": "t"}).json()["id"]
        with patch("routers.ai.embed_text", return_value=make_vector(seed)):
            return client.post("/v1/ask/stream", json={"question": "question", "session_id": session_id, "mode": "rag_only"})

    def test_users_own_ticket_transcript_is_retrievable(self, auth_client, db_session):
        me = auth_client.get("/v1/me").json()
        session = models.ChatSession(id_utilisateur=me["id"], status="closed")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        _seed_ticket_kb_entry(db_session, user_id=me["id"], session_id=session.id, seed=7, contenu="Mon transcript personnel xyz123")

        resp = self._ask(auth_client, seed=7)

        assert resp.status_code == 200
        assert "xyz123" in resp.text

    def test_another_users_ticket_transcript_is_not_leaked(self, auth_client, db_session):
        other = _make_user(db_session, email="leak_victim@example.com")
        other_session = _make_session(db_session, other)
        _seed_ticket_kb_entry(db_session, user_id=other.id, session_id=other_session.id, seed=8, contenu="Transcript secret456 de l'autre client")

        resp = self._ask(auth_client, seed=8)

        assert resp.status_code == 200
        assert "secret456" not in resp.text
        assert "Aucun contexte disponible" in resp.text

    def test_sav_agent_can_see_another_users_ticket_transcript(self, client, mark_verified, db_session):
        client.post("/v1/register", json={
            "username": "agent_view", "email": "agent_view@example.com",
            "password": _TEST_PASSWORD, "prenom": "A", "nom": "V",
        })
        mark_verified("agent_view@example.com")
        agent_token = client.post("/v1/login", json={"email": "agent_view@example.com", "password": _TEST_PASSWORD}).json()["access_token"]
        agent_id = client.get("/v1/me", headers={"Authorization": f"Bearer {agent_token}"}).json()["id"]

        admin_client = _make_admin_client(client, mark_verified)  # bascule client.headers vers l'admin temporaire
        promote = admin_client.put(f"/v1/users/{agent_id}/role", json={"role": "sav"})
        assert promote.status_code == 200, promote.json()

        other = _make_user(db_session, email="leak_source@example.com")
        other_session = _make_session(db_session, other)
        _seed_ticket_kb_entry(db_session, user_id=other.id, session_id=other_session.id, seed=9, contenu="Transcript visible789 par un agent")

        client.headers.update({"Authorization": f"Bearer {agent_token}"})  # bascule sur le compte sav
        resp = self._ask(client, seed=9)

        assert resp.status_code == 200
        assert "visible789" in resp.text

    def test_documents_ingested_normally_remain_reachable_by_everyone(self, auth_client, db_session):
        """source_user_id NULL (ingestion normale, pas un ticket) -- jamais concerné par le filtre."""
        db_session.add(models.KnowledgeBase(
            contenu="FAQ publique : livraison sous 48h.", embedding=make_vector(10), category="faq", source="faq.md",
        ))
        db_session.commit()

        resp = self._ask(auth_client, seed=10)

        assert resp.status_code == 200
        assert "livraison" in resp.text.lower()
