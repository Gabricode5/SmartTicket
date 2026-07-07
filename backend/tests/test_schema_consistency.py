"""Verifies backend/db/init-db.sql stays in sync with models.py.

Loads init-db.sql into a dedicated, disposable Postgres schema (isolated from
the tables the rest of the suite uses) and compares the resulting tables and
columns against what SQLAlchemy's Base.metadata declares.
"""
from pathlib import Path

from sqlalchemy import inspect

import models  # noqa: F401 -- registers all model tables on Base.metadata
from database import Base, engine

INIT_SQL_PATH = Path(__file__).resolve().parent.parent / "db" / "init-db.sql"
TEST_SCHEMA = "schema_consistency_check"


def _load_init_sql_into_schema() -> None:
    sql = INIT_SQL_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
        conn.exec_driver_sql(f"CREATE SCHEMA {TEST_SCHEMA}")
        # Keep "public" on the search_path so init-db.sql's unqualified
        # references to the vector/pgcrypto extensions (installed in public)
        # still resolve, while new tables land in our disposable schema.
        conn.exec_driver_sql(f"SET search_path TO {TEST_SCHEMA}, public")
        conn.exec_driver_sql(sql)


def _drop_schema() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")


def test_init_db_sql_matches_models():
    """init-db.sql must declare every table/column that models.py expects.

    init-db.sql is only allowed to be a subset of the runtime schema — the
    startup ALTER TABLE block in main.py exists precisely to upgrade
    already-deployed databases — but it must never drift from models.py
    again for *fresh* installs.
    """
    _load_init_sql_into_schema()
    try:
        inspector = inspect(engine)
        actual_tables = {
            table_name: {col["name"] for col in inspector.get_columns(table_name, schema=TEST_SCHEMA)}
            for table_name in inspector.get_table_names(schema=TEST_SCHEMA)
        }

        problems = []
        for table_name, table in Base.metadata.tables.items():
            if table_name not in actual_tables:
                problems.append(f"table '{table_name}' absente de init-db.sql")
                continue
            missing_columns = {c.name for c in table.columns} - actual_tables[table_name]
            for column in sorted(missing_columns):
                problems.append(f"colonne '{table_name}.{column}' absente de init-db.sql")

        assert not problems, (
            "init-db.sql est désynchronisé de models.py :\n- " + "\n- ".join(problems)
        )
    finally:
        _drop_schema()
