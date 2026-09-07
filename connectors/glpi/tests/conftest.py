"""Fixtures des tests connecteur.

- `glpi_client` / `test_config` : purs (fixtures JSON, aucune base).
- `test_store` / `test_poller` : fixture `db` -> Postgres pour `processed_tickets`
  (pgvector inutile ici). CONNECTOR_TEST_DATABASE_URL doit contenir "test".
"""
import os

import pytest

os.environ.setdefault("MISTRAL_API_KEY", "dummy-for-tests")
os.environ.setdefault("GLPI_URL", "https://glpi.test.local/apirest.php")
os.environ.setdefault("GLPI_APP_TOKEN", "app-token-test")
os.environ.setdefault("GLPI_USER_TOKEN", "user-token-test")

CONN_TEST_DB = os.environ.get(
    "CONNECTOR_TEST_DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/connector_test"
)
if "test" not in CONN_TEST_DB.lower():
    raise RuntimeError(f"CONNECTOR_TEST_DATABASE_URL ne ressemble pas à une base de test : {CONN_TEST_DB!r}")
os.environ["CONNECTOR_DATABASE_URL"] = CONN_TEST_DB

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import glpi_connector.models  # noqa: E402,F401  (enregistre ProcessedTicket sur Base)
from glpi_connector.db import Base  # noqa: E402

_engine = create_engine(CONN_TEST_DB)
_Session = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session")
def _schema():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db(_schema):
    with _engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE processed_tickets RESTART IDENTITY CASCADE"))
        conn.commit()
    session = _Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def new_db_session(_schema):
    """Ouvre une session DB fraîche (simulateur de redémarrage du worker : même base,
    nouvelle session/process)."""

    def _open():
        return _Session()

    return _open
