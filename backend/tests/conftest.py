import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("MISTRAL_API_KEY", "dummy")

# TEST_DATABASE_URL is intentionally separate from DATABASE_URL (the app's prod/dev DB).
# Tests will refuse to run if this variable is not set or does not contain "test".
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test_db")

if "test" not in TEST_DB_URL.lower():
    raise RuntimeError(
        f"TEST_DATABASE_URL does not look like a test database: {TEST_DB_URL!r}\n"
        "Refusing to run tests to avoid wiping a real database."
    )

# Point the app at the test DB before any app module is imported.
os.environ["DATABASE_URL"] = TEST_DB_URL

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database import Base, get_db
from main import app
import models
engine = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_TRUNCATE_SQL = text(
    "TRUNCATE TABLE knowledge_base, chat_messages, chat_sessions, utilisateur RESTART IDENTITY CASCADE"
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create schema and extensions once for the whole test session."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _seed_roles()
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_roles():
    with TestingSessionLocal() as session:
        for role_name in ["user", "sav", "admin"]:
            if not session.query(models.Role).filter_by(nom_role=role_name).first():
                session.add(models.Role(nom_role=role_name))
        session.commit()


@pytest.fixture(autouse=True)
def clean_tables(setup_database):
    """Wipe user data before each test so tests are fully independent."""
    with engine.connect() as conn:
        conn.execute(_TRUNCATE_SQL)
        conn.commit()
    yield


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    """Creates a standard user and returns their credentials."""
    payload = {
        "username": "fixture_user",
        "email": "fixture@example.com",
        "password": "password123",
        "prenom": "Fixture",
        "nom": "User",
    }
    client.post("/v1/register", json=payload)
    return payload


@pytest.fixture
def auth_client(client, registered_user):
    """Returns a TestClient with a valid JWT token already set."""
    resp = client.post("/v1/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
