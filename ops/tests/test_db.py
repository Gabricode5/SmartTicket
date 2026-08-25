"""Tests du registre local instances.db (ops/db.py) — se concentre sur la migration des
colonnes CRM ajoutées après la création initiale de la table (2026-08-25) : init_db() doit
mettre à niveau un fichier existant créé avec l'ancien schéma sans perdre de données, y
compris la colonne `notes` technique (diagnostics Render), distincte des nouvelles colonnes
CRM et jamais touchée par cette migration."""
import sqlite3

import db

_LEGACY_SCHEMA = """
CREATE TABLE instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    render_backend_service_id TEXT,
    render_frontend_service_id TEXT,
    render_database_id TEXT,
    backend_url TEXT,
    frontend_url TEXT,
    subdomain TEXT,
    vendor_key TEXT,
    admin_setup_key TEXT,
    plan_tarifaire TEXT,
    statut TEXT NOT NULL DEFAULT 'provisioning',
    date_creation TEXT NOT NULL DEFAULT (datetime('now')),
    date_facturation TEXT,
    notes TEXT
);
"""


def _create_legacy_db(path):
    conn = sqlite3.connect(path)
    conn.execute(_LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO instances (client_name, slug, statut, notes) VALUES (?, ?, ?, ?)",
        ("Legacy Co", "legacy-co", "active", "backend-orphan-id-123"),
    )
    conn.commit()
    conn.close()


def test_init_db_adds_crm_columns_to_a_preexisting_legacy_schema_file(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    _create_legacy_db(path)
    monkeypatch.setattr(db, "DB_PATH", path)

    db.init_db()

    with db.get_connection() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(instances)")}
    for column in ("contact_name", "contact_email", "contact_phone", "crm_notes"):
        assert column in columns


def test_init_db_migration_preserves_existing_rows_and_technical_notes(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    _create_legacy_db(path)
    monkeypatch.setattr(db, "DB_PATH", path)

    db.init_db()

    row = db.get_instance("legacy-co")
    assert row["client_name"] == "Legacy Co"
    assert row["notes"] == "backend-orphan-id-123"  # diagnostic technique intact
    assert row["contact_name"] is None
    assert row["contact_email"] is None
    assert row["contact_phone"] is None
    assert row["crm_notes"] is None


def test_init_db_is_idempotent_on_a_database_already_migrated(tmp_path, monkeypatch):
    """Un second appel à init_db() (ex: redémarrage du serveur) ne doit pas planter en
    tentant de rajouter des colonnes déjà présentes."""
    path = tmp_path / "instances.db"
    monkeypatch.setattr(db, "DB_PATH", path)

    db.init_db()
    db.insert_instance(client_name="Acme", slug="acme", statut="active", contact_name="Jean Dupont")
    db.init_db()

    row = db.get_instance("acme")
    assert row["contact_name"] == "Jean Dupont"


def test_crm_fields_are_nullable_and_do_not_break_insert_without_them(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "instances.db")
    db.init_db()

    db.insert_instance(client_name="Acme", slug="acme", statut="active")

    row = db.get_instance("acme")
    assert row["contact_name"] is None
    assert row["contact_email"] is None
    assert row["contact_phone"] is None
    assert row["crm_notes"] is None
