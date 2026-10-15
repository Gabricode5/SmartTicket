"""Schema de la base vectorielle rag_core.

Version autonome et allegee de backend/models.py::KnowledgeBase : on garde le coeur
(contenu + embedding + source/category) et on laisse tomber tout ce qui est propre a
Tiqia (source_message_id, source_user_id, source_session_id, liens FK vers chat_*).

Le feedback vit ICI, sur le chunk (feedback_score), et non dans une table de messages
comme cote Tiqia : la passerelle l'incremente/decremente quand un agent valide ou rejette
une suggestion. Le reranking (rag_core.reranking) le lit pour la mise en quarantaine.
"""
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from rag_core.config import EMBEDDING_DIMENSION, TENANT_ID
from rag_core.db import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"

    id = Column(Integer, primary_key=True, index=True)
    contenu = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=False)
    source = Column(String(500), nullable=True)
    category = Column(String(50), nullable=True)
    # Feedback net accumule sur ce chunk (somme de +1 / -1). Lu par le reranking : un
    # chunk trop negatif (<= RERANK_QUARANTINE_THRESHOLD) est exclu du contexte.
    feedback_score = Column(Integer, nullable=False, server_default="0")
    # Mono-tenant strict : valeur fixe, jamais filtree. Presente pour parite de schema.
    tenant_id = Column(
        UUID(as_uuid=True), nullable=False, server_default=str(TENANT_ID), index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
