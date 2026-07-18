"""Base de suivi des instances clientes (SQLite, locale au poste du vendeur).

SQLite plutôt qu'un Postgres dédié (contrairement à ce qu'envisageait la première version
du plan dans docs/FLEET_PROVISIONING_PLAN.md) : à l'échelle visée ici (1-5 clients, gestion
en CLI + une requête SQL, zéro interface graphique), provisionner et payer un Postgres
managé rien que pour une poignée de lignes est disproportionné. Un fichier SQLite versionné
nulle part (cf. .gitignore racine, *.db déjà ignoré), sauvegardable en copiant un seul
fichier, consultable avec `sqlite3 ops/instances.db "SELECT * FROM instances"` — exactement
ce que décrit "CLI + une requête SQL". Migration vers Postgres envisageable plus tard si le
volume ou le besoin d'accès concurrent le justifie, pas avant.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "instances.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS instances (
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
# statut : provisioning | active | suspendue | supprimee | failed | deletion_failed


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(_SCHEMA)


def slug_exists(slug: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM instances WHERE slug = ?", (slug,)).fetchone()
        return row is not None


def insert_instance(**fields) -> int:
    columns = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO instances ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        return cursor.lastrowid


def update_instance(slug: str, **fields) -> None:
    """Met à jour une partie des colonnes d'une instance déjà présente. Utilisé par
    provision() (ops/provision_client.py) pour persister chaque ID de ressource Render dès
    sa création, pas seulement à la toute fin — pour qu'un crash en cours de route laisse
    toujours une trace exploitable dans instances.db. Comme insert_instance(), `fields` n'est
    interpolé dans le SQL que pour les NOMS de colonnes, toujours fournis en dur par l'appelant
    (jamais depuis une entrée utilisateur) — les VALEURS restent paramétrées."""
    if not fields:
        return
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE instances SET {set_clause} WHERE slug = ?", (*fields.values(), slug))


def get_instance(slug: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM instances WHERE slug = ?", (slug,)).fetchone()


def list_instances(statut: str | None = None) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if statut:
            return conn.execute("SELECT * FROM instances WHERE statut = ? ORDER BY date_creation", (statut,)).fetchall()
        return conn.execute("SELECT * FROM instances ORDER BY date_creation").fetchall()


def update_instance_status(slug: str, statut: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE instances SET statut = ? WHERE slug = ?", (statut, slug))


def delete_instance_row(slug: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM instances WHERE slug = ?", (slug,))
