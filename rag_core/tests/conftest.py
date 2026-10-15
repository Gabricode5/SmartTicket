"""Fixtures de test rag_core.

- Les tests PURS (catalogue, prompt, reranking, factory) ne touchent pas Postgres.
- Les tests de retrieval/pipeline demandent la fixture `db`, qui exige un Postgres+pgvector
  de test. RAG_TEST_DATABASE_URL doit contenir "test" (garde-fou anti-ecrasement, meme
  logique que backend/tests/conftest.py).
"""
import os

import pytest

os.environ.setdefault("MISTRAL_API_KEY", "dummy-for-tests")

RAG_TEST_DB_URL = os.environ.get(
    "RAG_TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test_db"
)
if "test" not in RAG_TEST_DB_URL.lower():
    raise RuntimeError(
        f"RAG_TEST_DATABASE_URL ne ressemble pas a une base de test : {RAG_TEST_DB_URL!r}"
    )
# Doit etre pose AVANT le premier import de rag_core.db.
os.environ["RAG_DATABASE_URL"] = RAG_TEST_DB_URL

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import rag_core.models  # noqa: E402,F401  (enregistre KnowledgeChunk sur Base)
from rag_core.db import Base  # noqa: E402

_engine = create_engine(RAG_TEST_DB_URL)
_Session = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session")
def _schema():
    with _engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db(_schema):
    with _engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE knowledge_chunk RESTART IDENTITY CASCADE"))
        conn.commit()
    session = _Session()
    try:
        yield session
    finally:
        session.close()
