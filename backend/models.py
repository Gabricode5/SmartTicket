from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Sequence, CheckConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from constants import DEFAULT_TENANT_ID
from database import Base

# Colonne posée sur chaque table principale en préparation d'un futur multi-tenant (cf.
# DEFAULT_TENANT_ID dans constants.py) — une seule valeur fixe par instance aujourd'hui,
# non exploitée dans les requêtes tant que le déploiement reste mono-tenant.
def _tenant_id_column():
    return Column(UUID(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID,
                   server_default=str(DEFAULT_TENANT_ID), index=True)

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
    email_verified = Column(Boolean, nullable=False, server_default="false")
    # Amorçage admin sans mot de passe transmis en clair (flotte d'instances, cf.
    # ops/provision_client.py) : posé uniquement à la création du compte quand
    # ADMIN_SETUP_TOKEN est fourni (main.py::run_migrations), jamais régénéré ensuite.
    # admin_setup_token n'est JAMAIS exposé dans un schéma Pydantic — c'est un secret
    # transitoire, à usage unique (used_at) et expirant (expires_at).
    admin_setup_token = Column(String(64), nullable=True)
    admin_setup_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    admin_setup_token_used_at = Column(DateTime(timezone=True), nullable=True)
    tenant_id = _tenant_id_column()
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    role = relationship("Role")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    id_utilisateur = Column(Integer, ForeignKey("utilisateur.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, server_default="open")  # open | transferred | closed
    transfer_reason = Column(String(50), nullable=True)  # technique | complexe | sensible | autre
    tenant_id = _tenant_id_column()
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    messages = relationship("ChatMessage", cascade="all, delete-orphan", passive_deletes=True)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    id_session = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    type_envoyeur = Column(String(10), nullable=False)
    contenu = Column(Text, nullable=False)
    feedback = Column(Integer, nullable=True)  # 1=👍, -1=👎, NULL=no feedback
    source_kb_ids = Column(ARRAY(Integer), nullable=True)  # chunks knowledge_base utilisés pour cette réponse IA
    tenant_id = _tenant_id_column()
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    id_utilisateur = Column(Integer, ForeignKey("utilisateur.id", ondelete="CASCADE"), nullable=False)
    id_session = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True)
    type = Column(String(30), nullable=False)  # sav_reply | session_transferred
    message = Column(String(255), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    tenant_id = _tenant_id_column()
    date_creation = Column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    """Un ticket par CYCLE de transfert IA→humain, pas un par conversation (cf. ROADMAP.md,
    chantier "refonte ticketing SAV", décision validée le 2026-08-17) : une session peut être
    transférée, résolue puis re-transférée plus tard — chaque transfert crée un nouveau ticket
    numéroté, session_id n'est PAS unique.

    reason et context_cutoff_message_id ajoutés à l'Étape 2 (2026-08-18), après vérification
    du flux de transfert réel : session.transfer_reason est EFFACÉ par resolve_session()
    (routers/sessions.py) dès que la session repasse "open" -- le référencer en lecture (comme
    envisagé à l'Étape 1) aurait perdu la raison historique du ticket dès sa résolution. reason
    est donc un snapshot immuable, posé une seule fois à la création. context_cutoff_message_id
    (id du dernier ChatMessage existant juste avant CE transfert, capturé avant l'insertion du
    message système "vous avez été mis en relation") isole le contexte IA propre à CE cycle --
    un id de message, monotone et sans ambiguïté, plutôt que created_at (aucune garantie
    d'ordre entre deux inserts quasi simultanés, et ne suffit de toute façon pas à borner
    plusieurs cycles de transfert sur la même session)."""
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(Integer, Sequence("ticket_number_seq", start=1000), nullable=False, unique=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, server_default="new", index=True)  # new | in_progress | resolved | closed
    # Dimension INDÉPENDANTE de status (un ticket peut être in_progress + waiting_on=customer
    # en même temps) : de qui on attend la prochaine action.
    waiting_on = Column(String(20), nullable=False, server_default="us", index=True)  # us | customer
    assigned_agent_id = Column(Integer, ForeignKey("utilisateur.id", ondelete="SET NULL"), nullable=True, index=True)
    priority = Column(String(10), nullable=False, server_default="normal")  # normal | urgent
    reason = Column(String(50), nullable=True)  # snapshot de transfer_reason à la création (technique/complexe/sensible/autre)
    context_cutoff_message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    tenant_id = _tenant_id_column()
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('new','in_progress','resolved','closed')", name="ck_tickets_status"),
        CheckConstraint("waiting_on IN ('us','customer')", name="ck_tickets_waiting_on"),
        CheckConstraint("priority IN ('normal','urgent')", name="ck_tickets_priority"),
    )


class InstanceSubscription(Base):
    """Ligne unique (id=1) par instance — coupe-circuit d'abonnement pour le modèle
    "flotte d'instances" (cf. ROADMAP.md, section commercialisation) : l'opérateur héberge
    et paye Render pour chaque instance client, donc a besoin d'un moyen de couper l'accès
    si un client cesse de payer, sans dépendre des identifiants admin de ce client (qui sont
    justement contrôlés par la partie qui pourrait ne plus payer). Basculé exclusivement via
    un secret propre à l'opérateur (VENDOR_KEY, cf. dependencies.py), jamais via le rôle
    admin classique."""
    __tablename__ = "instance_subscription"

    id = Column(Integer, primary_key=True)
    status = Column(String(20), nullable=False, default="active")  # active | suspended
    reason = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AICallLog(Base):
    """best_match_distance / question_message_id ajoutés le 2026-08-19 (chantier "Partie
    admin : détecter les trous de la base de connaissances") : avant ça, rag_chunks_found==0
    était le SEUL signal disponible, et il ne capture que le cas où la base est vide ou
    l'embedding a échoué -- jamais le cas, bien plus fréquent, où la base contient des chunks
    mais AUCUN n'est réellement pertinent (rag_reranking.py ne rejette jamais par distance, il
    ne fait que réordonner : dès que la base a une ligne, l'IA génère toujours une réponse à
    partir des top-k chunks retournés, même sans rapport avec la question). best_match_distance
    capture la distance cosinus du meilleur candidat AVANT reranking (le reranking mélange
    feedback/recouvrement lexical, ce qui fausserait la mesure de pertinence pure). question_
    message_id référence chat_messages plutôt que de dupliquer le texte de la question ici --
    une seule copie de cette donnée potentiellement personnelle (RGPD)."""
    __tablename__ = "ai_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    id_session = Column(Integer, ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True)
    call_type = Column(String(20), nullable=False)
    model_name = Column(String(100), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    rag_chunks_found = Column(Integer, nullable=True)
    rag_context_chars = Column(Integer, nullable=True)
    best_match_distance = Column(Float, nullable=True)
    question_message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_type = Column(String(100), nullable=True)
    tenant_id = _tenant_id_column()
    date_creation = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    source_message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    contenu = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    category = Column(String(50), nullable=True)
    source = Column(String(500), nullable=True)
    tenant_id = _tenant_id_column()
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
