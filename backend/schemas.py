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
    email: EmailStr
    prenom: Optional[str]
    nom: Optional[str]
    role: str
    date_creation: datetime

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    prenom: Optional[str] = None
    nom: Optional[str] = None
    role: str

    class Config:
        from_attributes = True

class UserRoleUpdateRequest(BaseModel):
    role: str

class UserAdminUpdateRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
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
    email: EmailStr
    prenom: Optional[str] = None
    nom: Optional[str] = None
    role: str
    date_creation: datetime

class MeUpdateRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None

class MePasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str


class AskRequest(BaseModel):
    question: str = Field(..., description="Question envoyée au modèle Mistral AI")
    session_id: int = Field(..., description="ID de la session de chat active")
    mode: str = Field("rag_llm", description="rag_llm = RAG + génération LLM (défaut) ; rag_only = contexte brut sans génération")
