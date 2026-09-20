"""Tests de l'étape 4 du système de pôles (cf. feature/poles) : CRUD Pole, assignation
manager<->pôles, création d'utilisateur restreinte au pôle du manager.
"""
import contextlib
import os
import secrets
from unittest.mock import patch

import models
from dependencies import pwd_context

_TEST_PASSWORD = secrets.token_urlsafe(16)


@contextlib.contextmanager
def _poles_enabled():
    """POLES_ENABLED est importé par valeur dans dependencies.py (source), routers/poles.py
    et routers/users.py -- les trois doivent être patchés ensemble pour un scénario
    cohérent "flag actif", même pattern que routers.ai.POLES_ENABLED aux étapes 2-3."""
    with patch("dependencies.POLES_ENABLED", True), \
         patch("routers.poles.POLES_ENABLED", True), \
         patch("routers.users.POLES_ENABLED", True):
        yield


def _make_pole(db_session, *, nom: str, is_global: bool = False) -> models.Pole:
    pole = models.Pole(nom=nom, is_global=is_global)
    db_session.add(pole)
    db_session.commit()
    db_session.refresh(pole)
    return pole


def _make_admin_client(client, *, email: str = "poles_mgmt_admin@example.com"):
    client.post("/v1/setup-admin", json={
        "username": "poles_mgmt_admin", "email": email, "password": _TEST_PASSWORD,
    }, headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]})
    token = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD}).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _register_and_login(client, mark_verified, db_session, *, email: str, role: str = "user") -> int:
    resp = client.post("/v1/register", json={
        "username": email.split("@")[0], "email": email, "password": _TEST_PASSWORD,
    })
    assert resp.status_code == 201, resp.json()
    user_id = resp.json()["id"]
    mark_verified(email)
    if role != "user":
        user = db_session.query(models.Utilisateur).filter_by(id=user_id).first()
        role_row = db_session.query(models.Role).filter_by(nom_role=role).first()
        user.id_role = role_row.id
        db_session.commit()
    token = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD}).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return user_id


def _make_manager(db_session, *, email: str, pole_ids: list[int]) -> int:
    role_row = db_session.query(models.Role).filter_by(nom_role="superviseur").first()
    manager = models.Utilisateur(
        username=email.split("@")[0], email=email, password_hash=pwd_context.hash(_TEST_PASSWORD),
        id_role=role_row.id, email_verified=True,
    )
    db_session.add(manager)
    db_session.commit()
    db_session.refresh(manager)
    for pole_id in pole_ids:
        db_session.add(models.ManagerPole(manager_id=manager.id, pole_id=pole_id))
    db_session.commit()
    return manager.id


def _login_as(client, email: str) -> None:
    token = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD}).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})


# --------------------------------------------------------------------------------------
# 1. CRUD Pole -- réservé au super admin
# --------------------------------------------------------------------------------------

class TestPoleCrudAuthorization:
    def test_non_admin_cannot_create_a_pole(self, client, mark_verified, db_session):
        _register_and_login(client, mark_verified, db_session, email="crud-user@example.com")
        with _poles_enabled():
            resp = client.post("/v1/poles", json={"nom": "Support"})
        assert resp.status_code == 403

    def test_non_admin_cannot_delete_a_pole(self, client, mark_verified, db_session):
        pole = _make_pole(db_session, nom="Pôle à supprimer")
        _register_and_login(client, mark_verified, db_session, email="crud-user-del@example.com")
        with _poles_enabled():
            resp = client.delete(f"/v1/poles/{pole.id}")
        assert resp.status_code == 403

    def test_superviseur_manager_cannot_manage_poles(self, client, mark_verified, db_session):
        """Un manager gère SES pôles pour l'ingestion/création d'utilisateurs, mais ne
        gère jamais les pôles eux-mêmes -- seul le super admin (décision : "seul l'admin
        gère les pôles et assigne les managers")."""
        pole = _make_pole(db_session, nom="Pôle géré par manager")
        manager_id = _make_manager(db_session, email="crud-manager@example.com", pole_ids=[pole.id])
        _login_as(client, "crud-manager@example.com")
        with _poles_enabled():
            resp = client.post("/v1/poles", json={"nom": "Nouveau pôle"})
        assert resp.status_code == 403
        assert manager_id  # évite le warning "unused"

    def test_admin_can_create_rename_and_delete_a_pole(self, client, db_session):
        _make_admin_client(client)
        with _poles_enabled():
            created = client.post("/v1/poles", json={"nom": "Support technique"})
            assert created.status_code == 201
            pole_id = created.json()["id"]

            renamed = client.put(f"/v1/poles/{pole_id}", json={"nom": "Support technique v2"})
            assert renamed.status_code == 200
            assert renamed.json()["nom"] == "Support technique v2"

            deleted = client.delete(f"/v1/poles/{pole_id}")
            assert deleted.status_code == 204

        assert db_session.query(models.Pole).filter_by(id=pole_id).first() is None


class TestGeneralPoleCannotBeDeleted:
    def test_deleting_the_global_pole_is_rejected(self, client, db_session):
        general = _make_pole(db_session, nom="Général", is_global=True)
        _make_admin_client(client)
        with _poles_enabled():
            resp = client.delete(f"/v1/poles/{general.id}")
        assert resp.status_code == 400
        assert db_session.query(models.Pole).filter_by(id=general.id).first() is not None

    def test_deleting_a_pole_reassigns_its_data_to_the_global_pole(self, client, db_session):
        """Correctif appliqué en étape 4 : knowledge_base.pole_id est NOT NULL depuis
        l'étape 3, un simple ON DELETE SET NULL échouerait. Les données et utilisateurs du
        pôle supprimé doivent être réaffectés à "Général", pas perdus."""
        general = _make_pole(db_session, nom="Général reassign", is_global=True)
        pole = _make_pole(db_session, nom="Pôle éphémère reassign")
        kb = models.KnowledgeBase(contenu="doc du pôle éphémère", embedding=[0.0] * 1024, pole_id=pole.id)
        db_session.add(kb)
        role_row = db_session.query(models.Role).filter_by(nom_role="sav").first()
        user = models.Utilisateur(
            username="reassign_sav", email="reassign-sav@example.com", password_hash="x",
            id_role=role_row.id, email_verified=True, pole_id=pole.id,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(kb)
        db_session.refresh(user)

        _make_admin_client(client)
        with _poles_enabled():
            resp = client.delete(f"/v1/poles/{pole.id}")
        assert resp.status_code == 204

        db_session.expire_all()
        assert db_session.query(models.KnowledgeBase).filter_by(id=kb.id).first().pole_id == general.id
        assert db_session.query(models.Utilisateur).filter_by(id=user.id).first().pole_id == general.id


# --------------------------------------------------------------------------------------
# 2. Assignation manager <-> pôles
# --------------------------------------------------------------------------------------

class TestManagerPoleAssignment:
    def test_admin_can_assign_a_superviseur_to_multiple_poles(self, client, mark_verified, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A assign")
        pole_b = _make_pole(db_session, nom="Pôle B assign")
        superviseur_id = _register_and_login(client, mark_verified, db_session, email="sup-assign@example.com", role="superviseur")
        _make_admin_client(client)

        with _poles_enabled():
            resp = client.put(f"/v1/users/{superviseur_id}/manager-poles", json={"pole_ids": [pole_a.id, pole_b.id]})

        assert resp.status_code == 200
        links = db_session.query(models.ManagerPole).filter_by(manager_id=superviseur_id).all()
        assert {link.pole_id for link in links} == {pole_a.id, pole_b.id}

    def test_cannot_assign_poles_to_a_non_superviseur(self, client, mark_verified, db_session):
        pole = _make_pole(db_session, nom="Pôle A non-sup")
        user_id = _register_and_login(client, mark_verified, db_session, email="not-a-sup@example.com", role="sav")
        _make_admin_client(client)

        with _poles_enabled():
            resp = client.put(f"/v1/users/{user_id}/manager-poles", json={"pole_ids": [pole.id]})

        assert resp.status_code == 400

    def test_cannot_assign_the_global_pole_to_a_manager(self, client, mark_verified, db_session):
        general = _make_pole(db_session, nom="Général assign", is_global=True)
        superviseur_id = _register_and_login(client, mark_verified, db_session, email="sup-global-assign@example.com", role="superviseur")
        _make_admin_client(client)

        with _poles_enabled():
            resp = client.put(f"/v1/users/{superviseur_id}/manager-poles", json={"pole_ids": [general.id]})

        assert resp.status_code == 400

    def test_non_admin_cannot_assign_manager_poles(self, client, mark_verified, db_session):
        pole = _make_pole(db_session, nom="Pôle A non-admin assign")
        superviseur_id = _register_and_login(client, mark_verified, db_session, email="sup-target@example.com", role="superviseur")
        _register_and_login(client, mark_verified, db_session, email="regular-assigner@example.com")

        with _poles_enabled():
            resp = client.put(f"/v1/users/{superviseur_id}/manager-poles", json={"pole_ids": [pole.id]})

        assert resp.status_code == 403


# --------------------------------------------------------------------------------------
# 3. Création d'utilisateur restreinte au pôle du manager (import CSV)
# --------------------------------------------------------------------------------------

class TestManagerScopedUserCreation:
    CSV_CONTENT = b"email,username\nnewbie@example.com,newbie\n"

    def test_manager_creates_user_in_their_own_pole(self, client, mark_verified, db_session):
        pole = _make_pole(db_session, nom="Pôle A csv")
        _make_manager(db_session, email="csv-manager@example.com", pole_ids=[pole.id])
        _login_as(client, "csv-manager@example.com")

        with _poles_enabled():
            resp = client.post(
                "/v1/users/import-csv",
                files={"file": ("users.csv", self.CSV_CONTENT, "text/csv")},
                data={"pole_id": str(pole.id)},
            )

        assert resp.status_code == 200, resp.json()
        assert resp.json()["created"] == 1
        created = db_session.query(models.Utilisateur).filter_by(email="newbie@example.com").first()
        assert created is not None
        assert created.pole_id == pole.id

    def test_manager_cannot_create_user_in_a_pole_they_do_not_manage(self, client, db_session):
        pole_a = _make_pole(db_session, nom="Pôle A csv géré")
        pole_b = _make_pole(db_session, nom="Pôle B csv non géré")
        _make_manager(db_session, email="csv-manager-restricted@example.com", pole_ids=[pole_a.id])
        _login_as(client, "csv-manager-restricted@example.com")

        with _poles_enabled():
            resp = client.post(
                "/v1/users/import-csv",
                files={"file": ("users.csv", self.CSV_CONTENT, "text/csv")},
                data={"pole_id": str(pole_b.id)},
            )

        assert resp.status_code == 403

    def test_manager_cannot_create_user_in_the_global_pole(self, client, db_session):
        general = _make_pole(db_session, nom="Général csv", is_global=True)
        pole_a = _make_pole(db_session, nom="Pôle A csv global")
        _make_manager(db_session, email="csv-manager-global@example.com", pole_ids=[pole_a.id])
        _login_as(client, "csv-manager-global@example.com")

        with _poles_enabled():
            resp = client.post(
                "/v1/users/import-csv",
                files={"file": ("users.csv", self.CSV_CONTENT, "text/csv")},
                data={"pole_id": str(general.id)},
            )

        assert resp.status_code == 403

    def test_admin_can_create_user_in_the_global_pole(self, client, db_session):
        general = _make_pole(db_session, nom="Général csv admin", is_global=True)
        _make_admin_client(client)

        with _poles_enabled():
            resp = client.post(
                "/v1/users/import-csv",
                files={"file": ("users.csv", self.CSV_CONTENT, "text/csv")},
                data={"pole_id": str(general.id)},
            )

        assert resp.status_code == 200, resp.json()
        created = db_session.query(models.Utilisateur).filter_by(email="newbie@example.com").first()
        assert created.pole_id == general.id

    def test_plain_superviseur_without_manager_poles_still_cannot_import(self, client, mark_verified, db_session):
        """import-csv était déjà strictement admin-only AVANT les pôles (cf.
        routers/users.py, vérif littérale role == "admin") -- un superviseur simple n'a
        jamais eu ce droit. La décision B ("garde son comportement actuel") s'applique à
        is_admin_or_sav (ingestion KB, filtre RAG), pas à cet endpoint qui était déjà plus
        restrictif : l'étendre à "manager" est une capacité NOUVELLE, pas une restauration."""
        _register_and_login(client, mark_verified, db_session, email="plain-sup-csv@example.com", role="superviseur")

        with _poles_enabled():
            resp = client.post(
                "/v1/users/import-csv",
                files={"file": ("users.csv", self.CSV_CONTENT, "text/csv")},
            )

        assert resp.status_code == 403


# --------------------------------------------------------------------------------------
# 4. Rétro-compatibilité -- flag off
# --------------------------------------------------------------------------------------

class TestManagementRetroCompat:
    def test_pole_endpoints_are_disabled_when_flag_is_off(self, client, db_session):
        _make_admin_client(client)
        resp = client.post("/v1/poles", json={"nom": "Ne devrait pas se créer"})
        assert resp.status_code == 403
        assert db_session.query(models.Pole).count() == 0

    def test_regular_sav_can_still_import_csv_when_flag_is_off(self, client, mark_verified, db_session):
        """Un compte sav (is_admin_or_sav) ne devient jamais "manager" sans POLES_ENABLED
        -- mais aujourd'hui import-csv est admin-only : vérifie qu'un sav reste bien 403,
        comportement identique à avant l'étape 4."""
        _register_and_login(client, mark_verified, db_session, email="plain-sav-retro@example.com", role="sav")
        resp = client.post(
            "/v1/users/import-csv",
            files={"file": ("users.csv", TestManagerScopedUserCreation.CSV_CONTENT, "text/csv")},
        )
        assert resp.status_code == 403

    def test_admin_import_csv_unaffected_when_flag_is_off(self, client, db_session):
        _make_admin_client(client)
        resp = client.post(
            "/v1/users/import-csv",
            files={"file": ("users.csv", TestManagerScopedUserCreation.CSV_CONTENT, "text/csv")},
        )
        assert resp.status_code == 200, resp.json()
        created = db_session.query(models.Utilisateur).filter_by(email="newbie@example.com").first()
        assert created is not None
        assert created.pole_id is None
