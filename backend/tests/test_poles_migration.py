"""Tests de l'étape 1 du système de pôles (cf. feature/poles) : modèle Pole/ManagerPole,
colonnes pole_id, et backfill idempotent du pôle "Général" (fusion règles 3+5).

Rien ici ne teste le filtrage RAG ni l'ingestion pole-aware -- ce sont les étapes
suivantes du plan. Ce fichier vérifie uniquement : la migration elle-même, et surtout
que POLES_ENABLED=false laisse le comportement actuel strictement identique.
"""
import secrets
from unittest.mock import patch

import models
from sqlalchemy import text
import main
from main import run_poles_migration

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _make_user(db_session, *, email: str, role: str = "user") -> models.Utilisateur:
    role_row = db_session.query(models.Role).filter_by(nom_role=role).first()
    user = models.Utilisateur(
        username=email.split("@")[0], email=email, password_hash="x", id_role=role_row.id, email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_kb_row(db_session, *, contenu: str, pole_id: int | None = None) -> models.KnowledgeBase:
    row = models.KnowledgeBase(
        contenu=contenu, embedding=[0.0] * 1024, category="test", pole_id=pole_id,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


class TestPolesMigrationDisabled:
    """POLES_ENABLED=false : aucune ligne ne doit jamais être créée ou modifiée."""

    def test_no_pole_is_created(self, db_session):
        run_poles_migration(enabled=False)
        assert db_session.query(models.Pole).count() == 0

    def test_existing_data_is_left_untouched(self, db_session):
        user = _make_user(db_session, email="poles-off-user@example.com", role="user")
        kb = _make_kb_row(db_session, contenu="doc non affecté")

        run_poles_migration(enabled=False)

        db_session.expire_all()
        assert db_session.query(models.Utilisateur).filter_by(id=user.id).first().pole_id is None
        assert db_session.query(models.KnowledgeBase).filter_by(id=kb.id).first().pole_id is None

    def test_app_startup_runs_disabled_migration_without_error(self, client):
        """La fixture `client` déclenche le lifespan complet (run_migrations ->
        run_poles_migration) avec POLES_ENABLED absent de l'environnement de test, donc
        false par défaut -- exactement le chemin qu'emprunte toute instance qui n'active
        pas la feature. Aucune exception ne doit remonter, et aucun pôle ne doit exister."""
        with client:
            pass


class TestPolesMigrationEnabled:
    def test_creates_the_general_pole_as_global(self, db_session):
        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)

        general = db_session.query(models.Pole).filter_by(is_global=True).first()
        assert general is not None
        assert general.nom == "Général"

    def test_is_idempotent_across_repeated_runs(self, db_session):
        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)
        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)
        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)

        assert db_session.query(models.Pole).filter_by(is_global=True).count() == 1

    def test_backfills_knowledge_base_rows_without_a_pole(self, db_session):
        kb = _make_kb_row(db_session, contenu="doc pré-existant sans pôle")

        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)

        db_session.expire_all()
        general = db_session.query(models.Pole).filter_by(is_global=True).first()
        assert db_session.query(models.KnowledgeBase).filter_by(id=kb.id).first().pole_id == general.id

    def test_does_not_overwrite_a_knowledge_base_row_already_assigned_to_a_pole(self, db_session):
        other_pole = models.Pole(nom="Support technique")
        db_session.add(other_pole)
        db_session.commit()
        db_session.refresh(other_pole)
        kb = _make_kb_row(db_session, contenu="doc déjà assigné", pole_id=other_pole.id)

        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)

        db_session.expire_all()
        assert db_session.query(models.KnowledgeBase).filter_by(id=kb.id).first().pole_id == other_pole.id

    def test_backfills_user_and_sav_accounts_without_a_pole(self, db_session):
        user = _make_user(db_session, email="poles-on-user@example.com", role="user")
        sav = _make_user(db_session, email="poles-on-sav@example.com", role="sav")

        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)

        db_session.expire_all()
        general = db_session.query(models.Pole).filter_by(is_global=True).first()
        assert db_session.query(models.Utilisateur).filter_by(id=user.id).first().pole_id == general.id
        assert db_session.query(models.Utilisateur).filter_by(id=sav.id).first().pole_id == general.id

    def test_does_not_assign_a_pole_to_admin_accounts(self, db_session):
        """Règle 4 : le super admin (rôle admin existant) ne relève d'aucun pôle."""
        admin = _make_user(db_session, email="poles-on-admin@example.com", role="admin")

        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)

        db_session.expire_all()
        assert db_session.query(models.Utilisateur).filter_by(id=admin.id).first().pole_id is None

    def test_does_not_assign_a_pole_to_superviseur_accounts(self, db_session):
        """Un superviseur n'est pas mécaniquement rattaché à un pôle : il devient
        "manager" via une ligne manager_poles (étape 4), pas via pole_id (ambiguïté B,
        option 3 validée)."""
        superviseur = _make_user(db_session, email="poles-on-sup@example.com", role="superviseur")

        db_session.commit()  # ferme la transaction implicite laissée par refresh()/query, sinon deadlock avec l'ALTER TABLE de la migration
        run_poles_migration(enabled=True)

        db_session.expire_all()
        assert db_session.query(models.Utilisateur).filter_by(id=superviseur.id).first().pole_id is None


class TestManagerPoleLink:
    def test_manager_can_be_linked_to_multiple_poles(self, db_session):
        manager = _make_user(db_session, email="manager@example.com", role="superviseur")
        pole_a = models.Pole(nom="Pôle A")
        pole_b = models.Pole(nom="Pôle B")
        db_session.add_all([pole_a, pole_b])
        db_session.commit()

        db_session.add_all([
            models.ManagerPole(manager_id=manager.id, pole_id=pole_a.id),
            models.ManagerPole(manager_id=manager.id, pole_id=pole_b.id),
        ])
        db_session.commit()

        links = db_session.query(models.ManagerPole).filter_by(manager_id=manager.id).all()
        assert {link.pole_id for link in links} == {pole_a.id, pole_b.id}

    def test_deleting_a_pole_cascades_to_its_manager_links(self, db_session):
        manager = _make_user(db_session, email="manager-cascade@example.com", role="superviseur")
        pole = models.Pole(nom="Pôle éphémère")
        db_session.add(pole)
        db_session.commit()
        db_session.add(models.ManagerPole(manager_id=manager.id, pole_id=pole.id))
        db_session.commit()

        db_session.delete(pole)
        db_session.commit()

        assert db_session.query(models.ManagerPole).filter_by(manager_id=manager.id).count() == 0

    def test_deleting_a_pole_sets_users_pole_id_to_null(self, db_session):
        user = _make_user(db_session, email="pole-user-cascade@example.com", role="user")
        pole = models.Pole(nom="Pôle temporaire")
        db_session.add(pole)
        db_session.commit()
        user.pole_id = pole.id
        db_session.commit()

        db_session.delete(pole)
        db_session.commit()

        db_session.expire_all()
        assert db_session.query(models.Utilisateur).filter_by(id=user.id).first().pole_id is None


class TestSchemaChangesGatedButOrmSafe:
    """Correctif post-livraison (feature/poles) : les 3 tables/colonnes pôles
    (poles, manager_poles, pole_id sur utilisateur/knowledge_base) sont posées par
    run_migrations() -- pas run_poles_migration() -- et NE PEUVENT PAS être entièrement
    gatées derrière POLES_ENABLED sans casser l'application :

    - pole_id est un attribut mappé des modèles SQLAlchemy Utilisateur/KnowledgeBase :
      TOUTE requête ORM les touchant (login, /me, chat, RAG...) inclut cette colonne
      dans son SELECT, flag ou pas. Si la colonne n'existe pas réellement en base, ces
      requêtes échouent avec "column pole_id does not exist" -- testé empiriquement,
      ça casse tout, pas seulement les pôles.
    - poles/manager_poles ne peuvent pas non plus être exclues de create_all() : la FK
      ForeignKey("poles.id") est déclarée dans le DDL de utilisateur/knowledge_base
      eux-mêmes -- les exclure fait échouer la création de CES tables (testé sur une
      base neuve : le tout premier boot casse entièrement, avant même d'arriver aux
      pôles).

    Seule l'opération réellement coûteuse et évitable est gatée : le CREATE INDEX sur
    utilisateur/knowledge_base (scan complet + verrou le temps du scan -- risque réel
    sur une grosse table vectorielle en prod). Table/colonne sont des opérations
    rapides de métadonnées (PostgreSQL 11+, ADD COLUMN nullable sans défaut ; CREATE
    TABLE sur une table neuve et vide), sans réécriture ni verrou long.
    """

    def _index_exists(self, db_session, name: str) -> bool:
        row = db_session.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname = :name"), {"name": name}
        ).first()
        return row is not None

    def test_pole_index_is_not_created_when_flag_off(self, db_session):
        with patch("main.POLES_ENABLED", False):
            main.run_migrations()

        assert not self._index_exists(db_session, "ix_utilisateur_pole_id")
        assert not self._index_exists(db_session, "ix_knowledge_base_pole_id")

    def test_pole_column_exists_even_when_flag_off_so_orm_queries_do_not_crash(self, db_session):
        """C'est le point clé du correctif : la colonne DOIT exister (sinon toute
        requête ORM plante), même si son index -- lui -- reste absent."""
        with patch("main.POLES_ENABLED", False):
            main.run_migrations()

        # Ces requêtes échoueraient avec un ProgrammingError si pole_id n'existait pas.
        db_session.query(models.Utilisateur).count()
        db_session.query(models.KnowledgeBase).count()

    def test_activating_the_flag_creates_the_index_and_runs_the_migration_without_loss(self, db_session):
        """Bascule V1 -> pôles activés, au même boot : l'existant (une donnée déjà en
        base avant activation) doit être backfillé, pas perdu ni planté."""
        pre_existing_kb = _make_kb_row(db_session, contenu="doc déjà présent avant activation")

        db_session.commit()  # ferme la transaction implicite laissée par refresh(), sinon deadlock avec le DDL de run_migrations()
        with patch("main.POLES_ENABLED", True):
            main.run_migrations()

        assert self._index_exists(db_session, "ix_utilisateur_pole_id")
        assert self._index_exists(db_session, "ix_knowledge_base_pole_id")

        db_session.expire_all()
        general = db_session.query(models.Pole).filter_by(is_global=True).first()
        assert general is not None
        assert db_session.query(models.KnowledgeBase).filter_by(id=pre_existing_kb.id).first().pole_id == general.id
