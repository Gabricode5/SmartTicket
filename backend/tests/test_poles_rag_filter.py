"""Tests de l'étape 2 du système de pôles (cf. feature/poles) : filtre RAG par pôle dans
routers/ai.py + dependencies.is_super_admin.

Suit le même protocole que test_rag_evaluation.py::TestRagRetrieval -- mode="rag_only"
(pas d'appel Mistral réel) et embed_text mocké pour forcer une distance cosinus connue.
"""
import math
import os
import secrets
from unittest.mock import patch

import models

EMBED_DIM = 1024
_TEST_PASSWORD = secrets.token_urlsafe(16)


def make_vector(seed: int = 0) -> list[float]:
    """Vecteur unitaire déterministe — même seed = même vecteur = distance cosinus 0."""
    raw = [math.sin(i * 0.1 + seed) for i in range(EMBED_DIM)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


def _seed_kb(db_session, *, contenu: str, seed: int, pole_id: int | None) -> models.KnowledgeBase:
    row = models.KnowledgeBase(contenu=contenu, embedding=make_vector(seed), category="test", pole_id=pole_id)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_pole(db_session, *, nom: str, is_global: bool = False) -> models.Pole:
    pole = models.Pole(nom=nom, is_global=is_global)
    db_session.add(pole)
    db_session.commit()
    db_session.refresh(pole)
    return pole


def _register_and_login(client, mark_verified, db_session, *, email: str, pole_id: int | None = None, role: str = "user") -> int:
    """Crée un compte (rôle user par défaut via /register), le vérifie, l'assigne à un
    pôle et/ou un rôle directement en base (pas d'API pour ça avant l'étape 4), puis
    bascule le `client` partagé sur son token. Retourne l'id utilisateur."""
    resp = client.post("/v1/register", json={
        "username": email.split("@")[0], "email": email, "password": _TEST_PASSWORD,
    })
    assert resp.status_code == 201, resp.json()
    user_id = resp.json()["id"]
    mark_verified(email)

    if pole_id is not None or role != "user":
        user = db_session.query(models.Utilisateur).filter_by(id=user_id).first()
        if pole_id is not None:
            user.pole_id = pole_id
        if role != "user":
            role_row = db_session.query(models.Role).filter_by(nom_role=role).first()
            user.id_role = role_row.id
        db_session.commit()

    token = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD}).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return user_id


def _create_session(client) -> int:
    me = client.get("/v1/me").json()
    return client.post("/v1/sessions", params={"user_id": me["id"]}, json={"title": "test"}).json()["id"]


def _ask(client, question: str) -> str:
    resp = client.post("/v1/ask/stream", json={
        "question": question, "session_id": _create_session(client), "mode": "rag_only",
    })
    assert resp.status_code == 200
    return resp.text


class TestPolesDisabledRetroCompat:
    """POLES_ENABLED=false (défaut de l'environnement de test) : le pole_id d'un document
    ne doit avoir strictement aucun effet, exactement comme avant l'étape 2."""

    def test_user_sees_a_document_from_a_different_pole_when_flag_is_off(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A (flag off)")
        pole_b = _make_pole(db_session, nom="Pôle B (flag off)")
        _seed_kb(db_session, contenu="Procédure exclusive au pôle B", seed=10, pole_id=pole_b.id)
        _register_and_login(client, mark_verified, db_session, email="off-user-a@example.com", pole_id=pole_a.id)

        with patch("routers.ai.embed_text", return_value=make_vector(seed=10)):
            text = _ask(client, "Quelle est la procédure ?")

        assert "Procédure exclusive au pôle B" in text


class TestPolesEnabledFiltering:
    def test_user_does_not_see_a_document_from_another_pole(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A")
        pole_b = _make_pole(db_session, nom="Pôle B")
        _seed_kb(db_session, contenu="Procédure exclusive au pôle B", seed=20, pole_id=pole_b.id)
        _register_and_login(client, mark_verified, db_session, email="on-user-a@example.com", pole_id=pole_a.id)

        with patch("routers.ai.embed_text", return_value=make_vector(seed=20)), \
             patch("routers.ai.POLES_ENABLED", True):
            text = _ask(client, "Quelle est la procédure ?")

        assert "Procédure exclusive au pôle B" not in text
        assert "Aucun contexte disponible" in text

    def test_user_sees_a_document_from_their_own_pole(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A bis")
        _seed_kb(db_session, contenu="Procédure propre au pôle A", seed=21, pole_id=pole_a.id)
        _register_and_login(client, mark_verified, db_session, email="on-user-a-own@example.com", pole_id=pole_a.id)

        with patch("routers.ai.embed_text", return_value=make_vector(seed=21)), \
             patch("routers.ai.POLES_ENABLED", True):
            text = _ask(client, "Quelle est la procédure ?")

        assert "Procédure propre au pôle A" in text

    def test_user_sees_the_global_pole_document(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A ter")
        # Nom volontairement différent de "Général" : évite toute collision avec le pôle
        # global que run_poles_migration() crée lui-même sous ce nom exact si
        # POLES_ENABLED=true est aussi positionné au niveau environnement (nom UNIQUE).
        # Seul is_global=true compte pour le filtre RAG, jamais le nom.
        general = _make_pole(db_session, nom="Pôle commun (test)", is_global=True)
        _seed_kb(db_session, contenu="Document commun à tous les pôles", seed=22, pole_id=general.id)
        _register_and_login(client, mark_verified, db_session, email="on-user-a-global@example.com", pole_id=pole_a.id)

        with patch("routers.ai.embed_text", return_value=make_vector(seed=22)), \
             patch("routers.ai.POLES_ENABLED", True):
            text = _ask(client, "Quel est le document commun ?")

        assert "Document commun à tous les pôles" in text

    def test_user_sees_an_unmigrated_document_with_no_pole(self, client, mark_verified, db_session):
        """pole_id IS NULL (pas encore migré/ingéré) est traité comme visible par tous,
        pas comme un pôle exclusif -- cf. models.KnowledgeBase.pole_id."""
        pole_a = _make_pole(db_session, nom="Pôle A quater")
        _seed_kb(db_session, contenu="Document jamais rattaché à un pôle", seed=23, pole_id=None)
        _register_and_login(client, mark_verified, db_session, email="on-user-a-unmigrated@example.com", pole_id=pole_a.id)

        with patch("routers.ai.embed_text", return_value=make_vector(seed=23)), \
             patch("routers.ai.POLES_ENABLED", True):
            text = _ask(client, "Quel est ce document ?")

        assert "Document jamais rattaché à un pôle" in text

    def test_super_admin_sees_documents_from_every_pole(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A quinquies")
        pole_b = _make_pole(db_session, nom="Pôle B quinquies")
        _seed_kb(db_session, contenu="Procédure du pôle A quinquies", seed=24, pole_id=pole_a.id)
        _seed_kb(db_session, contenu="Procédure du pôle B quinquies", seed=25, pole_id=pole_b.id)
        client.post("/v1/setup-admin", json={
            "username": "poles_admin", "email": "poles_admin@example.com", "password": _TEST_PASSWORD,
        }, headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]})
        token = client.post("/v1/login", json={
            "email": "poles_admin@example.com", "password": _TEST_PASSWORD,
        }).json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        with patch("routers.ai.embed_text", return_value=make_vector(seed=24)), \
             patch("routers.ai.POLES_ENABLED", True):
            text_a = _ask(client, "Procédure A ?")
        with patch("routers.ai.embed_text", return_value=make_vector(seed=25)), \
             patch("routers.ai.POLES_ENABLED", True):
            text_b = _ask(client, "Procédure B ?")

        assert "Procédure du pôle A quinquies" in text_a
        assert "Procédure du pôle B quinquies" in text_b
