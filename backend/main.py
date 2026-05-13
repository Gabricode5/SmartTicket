import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text as _text

import models
from database import engine as _engine
from routers import ai, analytics, auth, knowledge, messages, sessions, users

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_log = logging.getLogger(__name__)

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY manquante. Définis-la dans l'environnement.")

PURGE_RETENTION_DAYS = int(os.getenv("PURGE_RETENTION_DAYS", "30"))

app = FastAPI(
    title="CRM Intelligent API",
    description="API pour un gestionnaire de tickets avec intégration IA (Mistral AI + RAG sur pgvector).",
    version="1.0.0",
    openapi_tags=[
        {"name": "IA", "description": "Endpoints exposant le modèle Mistral AI et le pipeline RAG (Retrieval-Augmented Generation)."},
        {"name": "Base de connaissances", "description": "Indexation et gestion de la base de connaissances vectorielle (pgvector)."},
        {"name": "Sessions", "description": "Gestion des sessions de chat et transferts vers un agent humain."},
        {"name": "Messages", "description": "Lecture, création de messages et feedback utilisateur."},
        {"name": "Authentification", "description": "Inscription, connexion et gestion du profil utilisateur."},
        {"name": "Utilisateurs", "description": "Administration des comptes utilisateurs (admin uniquement)."},
        {"name": "Analytics", "description": "Statistiques et indicateurs de performance du service IA."},
    ],
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3005,http://localhost:3000").split(",")
    if origin.strip()
]
cors_origins = [
    origin if origin.startswith("http://") or origin.startswith("https://") else f"https://{origin}"
    for origin in cors_origins
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for _router in [auth.router, sessions.router, messages.router, ai.router, knowledge.router, users.router, analytics.router]:
    app.include_router(_router, prefix="/v1")


def purge_soft_deleted(retention_days: int = PURGE_RETENTION_DAYS) -> None:
    """Hard-delete rows soft-deleted more than retention_days ago (RGPD)."""
    from database import SessionLocal as _SessionLocal
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    try:
        with _SessionLocal() as db:
            # Sessions en premier — leurs messages cascadent via SQL
            deleted_sessions = db.query(models.ChatSession).filter(
                models.ChatSession.deleted_at.isnot(None),
                models.ChatSession.deleted_at < cutoff,
            ).delete(synchronize_session=False)

            # Utilisateurs — leurs sessions restantes cascadent via SQL
            deleted_users = db.query(models.Utilisateur).filter(
                models.Utilisateur.deleted_at.isnot(None),
                models.Utilisateur.deleted_at < cutoff,
            ).delete(synchronize_session=False)

            db.commit()
            if deleted_sessions or deleted_users:
                _log.info(
                    "RGPD purge: %d session(s) et %d utilisateur(s) supprimés définitivement (rétention %d j)",
                    deleted_sessions, deleted_users, retention_days,
                )
    except Exception as exc:
        _log.error("RGPD purge failed: %s", exc, exc_info=True)


@app.on_event("startup")
def run_migrations():
    try:
        from database import Base, SessionLocal as _SessionLocal
        with _engine.connect() as conn:
            conn.execute(_text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(bind=_engine)
        with _SessionLocal() as session:
            for role_name in ["user", "ai", "sav", "admin"]:
                if not session.query(models.Role).filter_by(nom_role=role_name).first():
                    session.add(models.Role(nom_role=role_name))
            session.commit()

            # Crée le compte admin configuré s'il n'existe pas encore
            from dependencies import pwd_context as _pwd
            admin_role = session.query(models.Role).filter_by(nom_role="admin").first()
            if admin_role:
                admin_email = os.getenv("ADMIN_EMAIL", "admin@smartticket.app")
                admin_username = os.getenv("ADMIN_USERNAME", "admin")
                admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
                if not session.query(models.Utilisateur).filter_by(email=admin_email).first():
                    # Évite les collisions de username
                    if session.query(models.Utilisateur).filter_by(username=admin_username).first():
                        admin_username = admin_username + "_admin"
                    session.add(models.Utilisateur(
                        username=admin_username,
                        email=admin_email,
                        password_hash=_pwd.hash(admin_password),
                        id_role=admin_role.id,
                    ))
                    session.commit()
                    _log.info("Compte admin créé : %s", admin_email)
        with _engine.connect() as conn:
            conn.execute(_text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS feedback INTEGER"))
            conn.execute(_text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS transfer_reason VARCHAR(50)"))
            conn.execute(_text("ALTER TABLE utilisateur ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
            conn.execute(_text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
            conn.commit()
    except Exception as exc:
        _log.error("Startup migration failed: %s", exc, exc_info=True)


@app.on_event("startup")
def start_purge_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        # Purge quotidienne à 03:00 UTC
        scheduler.add_job(purge_soft_deleted, "cron", hour=3, minute=0, id="rgpd_purge")
        scheduler.start()
        _log.info("Scheduler RGPD démarré — purge quotidienne à 03:00 UTC (rétention %d j)", PURGE_RETENTION_DAYS)
        # Purge immédiate au démarrage pour traiter les enregistrements déjà expirés
        purge_soft_deleted()
    except Exception as exc:
        _log.error("Scheduler startup failed: %s", exc, exc_info=True)


@app.get("/")
def read_root():
    return {"status": "Online", "message": "Le gestionnaire de tickets avec RAG est prêt"}
