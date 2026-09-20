"""Tests de l'étape 3 du système de pôles (cf. feature/poles) : ingestion pole-aware sur
les 3 chemins (URL, fichier, transcript de ticket clos) + autorisation manager.

Structure :
  - TestResolveIngestionPoleId : la fonction d'autorisation pure (dependencies.py), sans HTTP.
  - TestIngestFileWritesPoleId : ingest_file_to_postgres écrit bien pole_id sur la ligne.
  - TestIngestFileEndpointAuthorization : bout en bout via l'endpoint HTTP (mocké pour
    éviter tout appel Mistral réel), vérifie les 403 et succès selon le rôle/pôle.
  - TestClosedTicketTranscriptInheritsClientPole : décision D, sur le modèle de
    test_close_session_indexing.py.
  - TestIngestionRetroCompat : POLES_ENABLED=false -> comportement actuel identique.
"""
import os
import secrets
from unittest.mock import patch

import pytest
import models
from dependencies import PoleIngestionError, resolve_ingestion_pole_id

_TEST_PASSWORD = secrets.token_urlsafe(16)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def _make_pole(db_session, *, nom: str, is_global: bool = False) -> models.Pole:
    pole = models.Pole(nom=nom, is_global=is_global)
    db_session.add(pole)
    db_session.commit()
    db_session.refresh(pole)
    return pole


def _make_user(db_session, *, email: str, role: str = "user", pole_id: int | None = None) -> models.Utilisateur:
    role_row = db_session.query(models.Role).filter_by(nom_role=role).first()
    user = models.Utilisateur(
        username=email.split("@")[0], email=email, password_hash="x", id_role=role_row.id,
        email_verified=True, pole_id=pole_id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_manager(db_session, *, email: str, pole_ids: list[int]) -> models.Utilisateur:
    """Un manager = un superviseur avec >=1 ligne manager_poles (option 3, décision B)."""
    manager = _make_user(db_session, email=email, role="superviseur")
    for pole_id in pole_ids:
        db_session.add(models.ManagerPole(manager_id=manager.id, pole_id=pole_id))
    db_session.commit()
    return manager


def _register_and_login(client, mark_verified, db_session, *, email: str, pole_id: int | None = None, role: str = "user") -> int:
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


# --------------------------------------------------------------------------------------
# 1. resolve_ingestion_pole_id -- fonction pure, pas de HTTP
# --------------------------------------------------------------------------------------

class TestResolveIngestionPoleId:
    def test_returns_none_when_flag_disabled_regardless_of_role(self, db_session):
        admin = _make_user(db_session, email="flag-off-admin@example.com", role="admin")
        with patch("dependencies.POLES_ENABLED", False):
            assert resolve_ingestion_pole_id(db_session, admin, requested_pole_id=999) is None

    def test_super_admin_can_ingest_into_any_pole_including_global(self, db_session):
        admin = _make_user(db_session, email="admin-any@example.com", role="admin")
        pole_a = _make_pole(db_session, nom="Pôle A resolve")
        general = _make_pole(db_session, nom="Général resolve", is_global=True)

        with patch("dependencies.POLES_ENABLED", True):
            assert resolve_ingestion_pole_id(db_session, admin, requested_pole_id=pole_a.id) == pole_a.id
            assert resolve_ingestion_pole_id(db_session, admin, requested_pole_id=general.id) == general.id

    def test_super_admin_defaults_to_global_pole_when_unspecified(self, db_session):
        admin = _make_user(db_session, email="admin-default@example.com", role="admin")
        general = _make_pole(db_session, nom="Général default", is_global=True)

        with patch("dependencies.POLES_ENABLED", True):
            assert resolve_ingestion_pole_id(db_session, admin, requested_pole_id=None) == general.id

    def test_unmanaged_superviseur_behaves_like_super_admin(self, db_session):
        superviseur = _make_user(db_session, email="sup-unmanaged@example.com", role="superviseur")
        pole_a = _make_pole(db_session, nom="Pôle A sup")

        with patch("dependencies.POLES_ENABLED", True):
            assert resolve_ingestion_pole_id(db_session, superviseur, requested_pole_id=pole_a.id) == pole_a.id

    def test_manager_can_ingest_into_their_own_pole(self, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A manager")
        manager = _make_manager(db_session, email="manager-own@example.com", pole_ids=[pole_a.id])

        with patch("dependencies.POLES_ENABLED", True):
            assert resolve_ingestion_pole_id(db_session, manager, requested_pole_id=pole_a.id) == pole_a.id

    def test_manager_defaults_to_their_single_managed_pole(self, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A default manager")
        manager = _make_manager(db_session, email="manager-default@example.com", pole_ids=[pole_a.id])

        with patch("dependencies.POLES_ENABLED", True):
            assert resolve_ingestion_pole_id(db_session, manager, requested_pole_id=None) == pole_a.id

    def test_manager_with_multiple_poles_must_specify_one(self, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A multi")
        pole_b = _make_pole(db_session, nom="Pôle B multi")
        manager = _make_manager(db_session, email="manager-multi@example.com", pole_ids=[pole_a.id, pole_b.id])

        with patch("dependencies.POLES_ENABLED", True):
            with pytest.raises(PoleIngestionError):
                resolve_ingestion_pole_id(db_session, manager, requested_pole_id=None)
            assert resolve_ingestion_pole_id(db_session, manager, requested_pole_id=pole_b.id) == pole_b.id

    def test_manager_cannot_ingest_into_a_pole_they_do_not_manage(self, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A géré")
        pole_b = _make_pole(db_session, nom="Pôle B non géré")
        manager = _make_manager(db_session, email="manager-restricted@example.com", pole_ids=[pole_a.id])

        with patch("dependencies.POLES_ENABLED", True):
            with pytest.raises(PoleIngestionError):
                resolve_ingestion_pole_id(db_session, manager, requested_pole_id=pole_b.id)

    def test_manager_cannot_ingest_into_the_global_pole(self, db_session):
        """Décision E : seul l'admin ingère dans le pôle global, jamais un manager."""
        pole_a = _make_pole(db_session, nom="Pôle A décision E")
        general = _make_pole(db_session, nom="Général décision E", is_global=True)
        manager = _make_manager(db_session, email="manager-no-global@example.com", pole_ids=[pole_a.id])

        with patch("dependencies.POLES_ENABLED", True):
            with pytest.raises(PoleIngestionError):
                resolve_ingestion_pole_id(db_session, manager, requested_pole_id=general.id)

    def test_sav_can_only_ingest_into_their_own_pole(self, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A sav")
        pole_b = _make_pole(db_session, nom="Pôle B sav")
        sav = _make_user(db_session, email="sav-scoped@example.com", role="sav", pole_id=pole_a.id)

        with patch("dependencies.POLES_ENABLED", True):
            assert resolve_ingestion_pole_id(db_session, sav, requested_pole_id=None) == pole_a.id
            assert resolve_ingestion_pole_id(db_session, sav, requested_pole_id=pole_a.id) == pole_a.id
            with pytest.raises(PoleIngestionError):
                resolve_ingestion_pole_id(db_session, sav, requested_pole_id=pole_b.id)

    def test_sav_without_a_pole_cannot_ingest(self, db_session):
        sav = _make_user(db_session, email="sav-no-pole@example.com", role="sav", pole_id=None)

        with patch("dependencies.POLES_ENABLED", True):
            with pytest.raises(PoleIngestionError):
                resolve_ingestion_pole_id(db_session, sav, requested_pole_id=None)


# --------------------------------------------------------------------------------------
# 2. ingest_file_to_postgres -- écrit bien pole_id (pas de réseau, contenu texte direct)
# --------------------------------------------------------------------------------------

class TestIngestFileWritesPoleId:
    def test_ingested_file_row_has_the_given_pole_id(self, db_session):
        from ingest_postgres import ingest_file_to_postgres

        pole = _make_pole(db_session, nom="Pôle ingestion directe")

        with patch("ingest_postgres.embed_texts", return_value=[[0.0] * 1024]):
            ingest_file_to_postgres(
                b"Procedure de test suffisamment longue pour passer le filtre qualite des chunks de la base de connaissances.",
                "doc.txt", category="test", pole_id=pole.id,
            )

        row = db_session.query(models.KnowledgeBase).filter_by(source="doc.txt").first()
        assert row is not None
        assert row.pole_id == pole.id

    def test_ingested_file_row_has_no_pole_id_when_not_given(self, db_session):
        from ingest_postgres import ingest_file_to_postgres

        with patch("ingest_postgres.embed_texts", return_value=[[0.0] * 1024]):
            ingest_file_to_postgres(
                b"Autre procedure de test suffisamment longue pour le filtre qualite de la base de connaissances.",
                "doc2.txt", category="test",
            )

        row = db_session.query(models.KnowledgeBase).filter_by(source="doc2.txt").first()
        assert row is not None
        assert row.pole_id is None


# --------------------------------------------------------------------------------------
# 3. Endpoint HTTP POST /knowledge-base/ingest-file -- autorisation bout en bout
# --------------------------------------------------------------------------------------

class TestIngestFileEndpointAuthorization:
    def _upload(self, client, *, pole_id: int | None = None):
        data = {"category": "test"}
        if pole_id is not None:
            data["pole_id"] = str(pole_id)
        return client.post(
            "/v1/knowledge-base/ingest-file",
            files={"file": ("doc.txt", b"Contenu de test pour l'upload.", "text/plain")},
            data=data,
        )

    def test_manager_ingesting_into_a_pole_they_do_not_manage_is_forbidden(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A endpoint")
        pole_b = _make_pole(db_session, nom="Pôle B endpoint")
        _register_and_login(client, mark_verified, db_session, email="mgr-endpoint@example.com", role="superviseur")
        manager_id = db_session.query(models.Utilisateur).filter_by(email="mgr-endpoint@example.com").first().id
        db_session.add(models.ManagerPole(manager_id=manager_id, pole_id=pole_a.id))
        db_session.commit()

        with patch("dependencies.POLES_ENABLED", True):
            resp = self._upload(client, pole_id=pole_b.id)

        assert resp.status_code == 403

    def test_manager_ingesting_into_the_global_pole_is_forbidden(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A global endpoint")
        general = _make_pole(db_session, nom="Général endpoint", is_global=True)
        _register_and_login(client, mark_verified, db_session, email="mgr-global@example.com", role="superviseur")
        manager_id = db_session.query(models.Utilisateur).filter_by(email="mgr-global@example.com").first().id
        db_session.add(models.ManagerPole(manager_id=manager_id, pole_id=pole_a.id))
        db_session.commit()

        with patch("dependencies.POLES_ENABLED", True):
            resp = self._upload(client, pole_id=general.id)

        assert resp.status_code == 403

    def test_manager_ingesting_into_their_own_pole_succeeds(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A succès")
        _register_and_login(client, mark_verified, db_session, email="mgr-success@example.com", role="superviseur")
        manager_id = db_session.query(models.Utilisateur).filter_by(email="mgr-success@example.com").first().id
        db_session.add(models.ManagerPole(manager_id=manager_id, pole_id=pole_a.id))
        db_session.commit()

        with patch("dependencies.POLES_ENABLED", True), \
             patch("ingest_postgres.embed_texts", return_value=[[0.0] * 1024]):
            resp = self._upload(client, pole_id=pole_a.id)

        assert resp.status_code == 200

    def test_admin_ingesting_into_the_global_pole_succeeds(self, client, db_session):
        general = _make_pole(db_session, nom="Général admin succès", is_global=True)
        client.post("/v1/setup-admin", json={
            "username": "poles_ing_admin", "email": "poles_ing_admin@example.com", "password": _TEST_PASSWORD,
        }, headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]})
        token = client.post("/v1/login", json={
            "email": "poles_ing_admin@example.com", "password": _TEST_PASSWORD,
        }).json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        with patch("dependencies.POLES_ENABLED", True), \
             patch("ingest_postgres.embed_texts", return_value=[[0.0] * 1024]):
            resp = self._upload(client, pole_id=general.id)

        assert resp.status_code == 200

    def test_sav_ingesting_into_a_different_pole_than_their_own_is_forbidden(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A sav endpoint")
        pole_b = _make_pole(db_session, nom="Pôle B sav endpoint")
        _register_and_login(client, mark_verified, db_session, email="sav-endpoint@example.com", role="sav", pole_id=pole_a.id)

        with patch("dependencies.POLES_ENABLED", True):
            resp = self._upload(client, pole_id=pole_b.id)

        assert resp.status_code == 403


# --------------------------------------------------------------------------------------
# 4. Transcript de ticket clos -- hérite du pôle du CLIENT, pas de l'agent (décision D)
# --------------------------------------------------------------------------------------

class TestClosedTicketTranscriptInheritsClientPole:
    def test_transcript_pole_is_the_client_pole_not_the_closing_agents(self, client, mark_verified, db_session):
        client_pole = _make_pole(db_session, nom="Pôle du client")
        agent_pole = _make_pole(db_session, nom="Pôle de l'agent")

        client_id = _register_and_login(client, mark_verified, db_session, email="ticket-client@example.com", pole_id=client_pole.id)
        session_resp = client.post("/v1/sessions", params={"user_id": client_id}, json={"title": "Souci"})
        session_id = session_resp.json()["id"]
        client.post("/v1/messages", json={
            "id_session": session_id, "type_envoyeur": "user", "contenu": "J'ai un problème avec ma commande.",
        })

        _register_and_login(client, mark_verified, db_session, email="ticket-agent@example.com", role="sav", pole_id=agent_pole.id)

        with patch("routers.sessions.INDEX_CLOSED_TICKETS", True), \
             patch("routers.sessions.POLES_ENABLED", True), \
             patch("routers.sessions.generate_text", return_value="Résumé du ticket."), \
             patch("routers.sessions.embed_text", return_value=[0.0] * 1024):
            resp = client.post(f"/v1/sessions/{session_id}/close")

        assert resp.status_code == 200
        rows = db_session.query(models.KnowledgeBase).filter(models.KnowledgeBase.source_session_id == session_id).all()
        assert rows
        for row in rows:
            assert row.pole_id == client_pole.id


# --------------------------------------------------------------------------------------
# 5. Rétro-compatibilité -- flag off, comportement actuel strictement identique
# --------------------------------------------------------------------------------------

class TestIngestionRetroCompat:
    def test_manager_restricted_to_one_pole_can_ingest_into_any_pole_when_flag_off(self, client, mark_verified, db_session):
        """Preuve la plus directe de rétro-compat : la restriction manager n'existe QUE
        derrière POLES_ENABLED. Flag absent (défaut de l'environnement de test) -> même un
        pôle qu'il ne gère pas ne le bloque plus (aucune notion de pôle n'est appliquée)."""
        pole_a = _make_pole(db_session, nom="Pôle A retro")
        pole_b = _make_pole(db_session, nom="Pôle B retro")
        _register_and_login(client, mark_verified, db_session, email="mgr-retro@example.com", role="superviseur")
        manager_id = db_session.query(models.Utilisateur).filter_by(email="mgr-retro@example.com").first().id
        db_session.add(models.ManagerPole(manager_id=manager_id, pole_id=pole_a.id))
        db_session.commit()

        with patch("ingest_postgres.embed_texts", return_value=[[0.0] * 1024]):
            resp = client.post(
                "/v1/knowledge-base/ingest-file",
                files={"file": ("doc.txt", b"Contenu de test pour l'upload retro-compat.", "text/plain")},
                data={"category": "test", "pole_id": str(pole_b.id)},
            )

        assert resp.status_code == 200

    def test_ingested_row_has_no_pole_id_when_flag_off_even_if_requested(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A retro pole_id")
        _register_and_login(client, mark_verified, db_session, email="user-retro@example.com", role="sav")

        with patch("ingest_postgres.embed_texts", return_value=[[0.0] * 1024]):
            client.post(
                "/v1/knowledge-base/ingest-file",
                files={"file": ("retro.txt", b"Contenu de test suffisamment long pour verifier l'absence de pole_id sur la ligne.", "text/plain")},
                data={"category": "test", "pole_id": str(pole_a.id)},
            )

        row = db_session.query(models.KnowledgeBase).filter_by(source="retro.txt").first()
        assert row is not None
        assert row.pole_id is None
