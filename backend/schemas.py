#C'est la structure des données qui circulent (la validation Pydantic).

from pydantic import BaseModel, EmailStr, HttpUrl, Field
from datetime import datetime
from typing import Optional

# Modèle pour la création (ce que le Front envoie)
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    prenom: Optional[str] = None
    nom: Optional[str] = None

    class Config:
        from_attributes = True

# Modèle pour la réponse (ce que l'API renvoie, sans le mot de passe !)
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    prenom: Optional[str]
    nom: Optional[str]
    role: str
    email_verified: bool = False
    date_creation: datetime

    class Config:
        from_attributes = True


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class AdminSetupRequest(BaseModel):
    token: str
    username: str
    email: EmailStr
    password: str

class UserListResponse(BaseModel):
    id: int
    username: str
    email: str
    prenom: Optional[str] = None
    nom: Optional[str] = None
    role: str

    class Config:
        from_attributes = True

class UserRoleUpdateRequest(BaseModel):
    role: str

class CsvImportSkippedRow(BaseModel):
    row: int
    email: str
    reason: str

class CsvImportResponse(BaseModel):
    total_rows: int
    created: int
    skipped: list[CsvImportSkippedRow]

class UserAdminUpdateRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class ChatSessionCreate(BaseModel):
    title: Optional[str] = "Nouvelle conversation"

class ChatSessionResponse(BaseModel):
    id: int
    id_utilisateur: int
    title: Optional[str]
    status: str
    transfer_reason: Optional[str] = None
    date_creation: datetime
    has_sav_reply: Optional[bool] = False

    class Config:
        from_attributes = True

class SessionSearchResult(BaseModel):
    id: int
    id_utilisateur: int
    title: Optional[str]
    status: str
    transfer_reason: Optional[str] = None
    date_creation: datetime
    snippet: Optional[str] = None

    class Config:
        from_attributes = True

class TransferRequest(BaseModel):
    reason: str  # technique | complexe | sensible | autre

class TransferredSessionResponse(BaseModel):
    id: int
    title: Optional[str]
    status: str
    transfer_reason: Optional[str]
    date_creation: datetime
    username: str

    class Config:
        from_attributes = True

class ChatMessageCreate(BaseModel):
    id_session: int
    type_envoyeur: str
    contenu: str

class ChatMessageResponse(BaseModel):
    id: int
    id_session: int
    type_envoyeur: str
    contenu: str
    feedback: Optional[int] = None
    source_kb_ids: Optional[list[int]] = None
    date_creation: datetime

    class Config:
        from_attributes = True

class MessageFeedbackRequest(BaseModel):
    feedback: int  # must be 1 or -1

class KnowledgeIngestRequest(BaseModel):
    url: HttpUrl
    category: Optional[str] = None

class KnowledgeIngestResponse(BaseModel):
    status: str
    message: Optional[str] = None
    inserted: Optional[int] = None
    chunks: Optional[int] = None
    url: Optional[str] = None
    category: Optional[str] = None
    urls_scraped: Optional[int] = None
    job_id: Optional[str] = None

class KnowledgeSourceResponse(BaseModel):
    id: int
    name: Optional[str] = None
    source: str
    source_type: str
    category: Optional[str] = None
    chunks: int
    pages: Optional[int] = None
    date_creation: datetime

    class Config:
        from_attributes = True


class PdfIngestResponse(BaseModel):
    inserted: int
    chunks: int
    filename: str
    category: str
    pages: int

class MeResponse(BaseModel):
    id: int
    username: str
    email: str
    prenom: Optional[str] = None
    nom: Optional[str] = None
    role: str
    email_verified: bool = False
    is_guest: bool = False
    date_creation: datetime

class ClaimAccountRequest(BaseModel):
    email: EmailStr
    password: str

class MeUpdateRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None

class MePasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str


class NotificationResponse(BaseModel):
    id: int
    type: str
    message: str
    id_session: Optional[int] = None
    read: bool
    date_creation: datetime

class SubscriptionStatusResponse(BaseModel):
    status: str
    reason: Optional[str] = None
    updated_at: Optional[datetime] = None

class SubscriptionStatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class AskRequest(BaseModel):
    question: str = Field(..., description="Question envoyée au modèle Mistral AI")
    session_id: int = Field(..., description="ID de la session de chat active")
    mode: str = Field("rag_llm", description="rag_llm = RAG + génération LLM (défaut) ; rag_only = contexte brut sans génération")


class TicketResponse(BaseModel):
    id: int
    ticket_number: int
    session_id: int
    status: str
    waiting_on: str
    assigned_agent_id: Optional[int] = None
    priority: str
    reason: Optional[str] = None
    context_cutoff_message_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # Dénormalisés en lecture (jamais stockés sur tickets, cf. décision Étape 1 : pas de
    # dénormalisation de l'identité client) -- posés manuellement dans le router, pas par
    # from_attributes, d'où Optional avec défaut malgré des valeurs toujours présentes en
    # pratique côté endpoint.
    client_username: Optional[str] = None
    client_email: Optional[str] = None
    assigned_agent_username: Optional[str] = None

    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    page_size: int


class TicketStatusUpdateRequest(BaseModel):
    status: str  # new | in_progress | resolved | closed


class TicketWaitingOnUpdateRequest(BaseModel):
    waiting_on: str  # us | customer


class TicketAssignRequest(BaseModel):
    agent_id: Optional[int] = Field(None, description="Cible de l'assignation. Omis/null = l'appelant se l'assigne à lui-même.")
