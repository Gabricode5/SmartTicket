import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import models
from database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/login", auto_error=False)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
KB_TOP_K = int(os.getenv("KB_TOP_K", "10"))
KB_MAX_CONTEXT_CHARS = int(os.getenv("KB_MAX_CONTEXT_CHARS", "3000"))
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "4000"))
SUMMARY_MAX_MESSAGES = int(os.getenv("SUMMARY_MAX_MESSAGES", "50"))
TRANSCRIPT_MAX_CHARS = int(os.getenv("TRANSCRIPT_MAX_CHARS", "12000"))
TRANSCRIPT_CHUNK_SIZE = int(os.getenv("TRANSCRIPT_CHUNK_SIZE", "1000"))
TRANSCRIPT_CHUNK_OVERLAP = int(os.getenv("TRANSCRIPT_CHUNK_OVERLAP", "150"))

INGEST_JOBS: dict[str, dict] = {}


def sanitize_model_name(raw_value: str, fallback: str) -> str:
    normalized = (raw_value or "").replace(";", ",").strip()
    if not normalized:
        return fallback
    return normalized.split(",")[0].strip() or fallback


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0:
        return [text]
    step = max(1, size - max(0, overlap))
    return [text[i:i + size] for i in range(0, len(text), step)]


def sanitize_text(value: str) -> str:
    return value.replace("\x00", "").strip()


def build_rag_prompt(question: str, context: str) -> str:
    return f"""Tu es un assistant SAV. Réponds clairement et de façon professionnelle.
Si le contexte n'apporte pas la réponse, dis-le honnêtement.
Réponds en texte brut uniquement, sans markdown, sans listes en syntaxe markdown et sans liens au format [texte](url).

CONTEXTE (base de connaissances) :
{context or "Aucun contexte disponible."}

QUESTION :
{question}""".strip()


MISTRAL_MODEL = sanitize_model_name(os.getenv("MISTRAL_MODEL", "mistral-small-latest"), "mistral-small-latest")
EMBED_MODEL = sanitize_model_name(os.getenv("EMBED_MODEL", "mistral-embed"), "mistral-embed")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> str:
    if not token:
        token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Session expirée ou invalide")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Session expirée ou invalide")


def get_user_by_email(db: Session, email: str):
    return db.query(models.Utilisateur).filter(models.Utilisateur.email == email).first()


def is_admin_or_sav(user: models.Utilisateur | None) -> bool:
    if not user or not user.role:
        return False
    return user.role.nom_role in ["admin", "sav"]
