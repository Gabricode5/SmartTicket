"""Base d'état du connecteur (table processed_tickets).

Distincte de la base vectorielle rag_core (RAG_DATABASE_URL) ET de la base Tiqia.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from glpi_connector import config

if not config.CONNECTOR_DATABASE_URL:
    raise RuntimeError(
        "CONNECTOR_DATABASE_URL manquante (base d'état du connecteur, distincte de "
        "RAG_DATABASE_URL et de la base Tiqia)."
    )

engine = create_engine(config.CONNECTOR_DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
