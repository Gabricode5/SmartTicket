import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/login", auto_error=False)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# Stockage des compteurs de rate limiting. "memory://" fonctionne out-of-the-box mais
# est local à chaque instance et se réinitialise à chaque redémarrage — suffisant pour
# une seule instance (ex: plan Render gratuit/starter). Si l'app est scalée sur plusieurs
# instances, pointer RATE_LIMIT_STORAGE_URI vers le Redis déjà présent dans docker-compose
# (ex: "redis://redis:6379") pour un comptage partagé.
RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "5/minute")
ASK_RATE_LIMIT = os.getenv("ASK_RATE_LIMIT", "20/minute")
RESEND_VERIFICATION_RATE_LIMIT = os.getenv("RESEND_VERIFICATION_RATE_LIMIT", "3/hour")
FORGOT_PASSWORD_RATE_LIMIT = os.getenv("FORGOT_PASSWORD_RATE_LIMIT", "3/hour")
# Inscription publique (B2B2C) : sans limite, une inscription reste la seule action non
# protégée de tout le flux auth — porte ouverte au spam de comptes jetables.
REGISTER_RATE_LIMIT = os.getenv("REGISTER_RATE_LIMIT", "5/hour")

EMAIL_VERIFICATION_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFICATION_EXPIRE_HOURS", "48"))
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "60"))

limiter = Limiter(key_func=get_remote_address, storage_uri=RATE_LIMIT_STORAGE_URI)


def rate_limit_key_by_user(request: Request) -> str:
    """Regroupe les compteurs de rate limit par compte (JWT) plutôt que par IP,
    pour plafonner le coût Mistral par utilisateur même derrière une IP partagée.
    Retombe sur l'IP si la requête n'est pas authentifiée."""
    token = request.headers.get("authorization", "")
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    else:
        token = request.cookies.get("auth_token", "")
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                return f"user:{email}"
        except JWTError:
            pass
    return get_remote_address(request)


# Désactivé par défaut : indexer le transcript/résumé d'un ticket clos dans la base de
# connaissances partagée expose le contenu d'une conversation (potentiellement des données
# personnelles) aux futures questions de n'importe quel autre utilisateur — acceptable en
# usage B2B interne (collègues de confiance), mais un vrai risque de fuite entre clients
# finaux dans un contexte B2B2C (support public). À activer explicitement instance par
# instance si le cas d'usage s'y prête.
INDEX_CLOSED_TICKETS = os.getenv("INDEX_CLOSED_TICKETS", "false").lower() == "true"

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


def create_email_verification_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS)
    payload = {"sub": email, "user_id": user_id, "type": "email_verification", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_email_verification_token(token: str) -> dict:
    """Décode un token de vérification d'email. Le claim `type` distingue ce token d'un
    token d'accès JWT classique — un access_token ne doit jamais pouvoir vérifier un email."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Lien de vérification invalide ou expiré")
    if payload.get("type") != "email_verification":
        raise HTTPException(status_code=400, detail="Lien de vérification invalide ou expiré")
    return payload


def create_password_reset_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    payload = {"sub": email, "user_id": user_id, "type": "password_reset", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_password_reset_token(token: str) -> dict:
    """Même principe que decode_email_verification_token : le claim `type` empêche un
    access_token (ou un token de vérification d'email) d'être réutilisé pour réinitialiser
    un mot de passe."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Lien de réinitialisation invalide ou expiré")
    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Lien de réinitialisation invalide ou expiré")
    return payload


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
    return db.query(models.Utilisateur).filter(
        models.Utilisateur.email == email,
        models.Utilisateur.deleted_at.is_(None),
    ).first()


def is_admin_or_sav(user: models.Utilisateur | None) -> bool:
    """Accès aux fonctionnalités agent (sessions transférées, KB, analytics...).
    Un superviseur hérite de tout ce qu'un agent SAV peut faire."""
    if not user or not user.role:
        return False
    return user.role.nom_role in ["admin", "sav", "superviseur"]


def can_manage_sav_team(user: models.Utilisateur | None) -> bool:
    """Admin ou superviseur : peut promouvoir user->sav et sav->user, jamais admin."""
    if not user or not user.role:
        return False
    return user.role.nom_role in ["admin", "superviseur"]
