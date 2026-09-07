"""Schéma de la base d'état du connecteur."""
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from glpi_connector import config
from glpi_connector.db import Base


class ProcessedTicket(Base):
    """Un ticket GLPI déjà traité par le poller. Clé = l'id GLPI du ticket :
    garantit qu'un ticket n'est jamais retraité, y compris après redémarrage du worker
    (l'état vit en base, pas en mémoire du process)."""

    __tablename__ = "processed_tickets"

    glpi_ticket_id = Column(Integer, primary_key=True, autoincrement=False)
    # answered | dry_run | skipped_empty | error
    status = Column(String(32), nullable=False)
    followup_id = Column(Integer, nullable=True)          # id du ITILFollowup créé (mode réel)
    suggestion_chars = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)                  # message d'erreur éventuel
    tenant_id = Column(
        UUID(as_uuid=True), nullable=False, server_default=config.CONNECTOR_TENANT_ID, index=True
    )
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
