#C'est la structure de ta Base de données (les tables SQL).

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from database import Base 

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    nom_role = Column(String(20), unique=True, nullable=False)


class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    prenom = Column(String(50))
    nom = Column(String(50))
    id_role = Column(Integer, ForeignKey("roles.id"), server_default="1")
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    role = relationship("Role")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    id_utilisateur = Column(Integer, ForeignKey("utilisateur.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, server_default="open")  # open | transferred | closed
    transfer_reason = Column(String(50), nullable=True)  # technique | complexe | sensible | autre
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    messages = relationship("ChatMessage", cascade="all, delete-orphan", passive_deletes=True)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    id_session = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    type_envoyeur = Column(String(10), nullable=False)
    contenu = Column(Text, nullable=False)
    feedback = Column(Integer, nullable=True)  # 1=👍, -1=👎, NULL=no feedback
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    source_message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    contenu = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    category = Column(String(50), nullable=True)
    source = Column(String(500), nullable=True)
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
