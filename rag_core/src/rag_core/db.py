"""Connexion a la base vectorielle dediee de rag_core (RAG_DATABASE_URL).

JAMAIS la base de Tiqia : rag_core vise sa propre instance pgvector, provisionnee avec
l'installation client (on-premise) ou un Postgres local en dev.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from rag_core.config import RAG_DATABASE_URL

if not RAG_DATABASE_URL:
    raise RuntimeError(
        "RAG_DATABASE_URL manquante. Definis-la dans l'environnement "
        "(base pgvector dediee, distincte de celle de Tiqia)."
    )

engine = create_engine(RAG_DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session():
    """Generateur de session (usage type FastAPI Depends cote passerelle)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
