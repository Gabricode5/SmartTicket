import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text as _text

import models
from database import engine as _engine
from dependencies import limiter
from routers import ai, analytics, auth, knowledge, messages, notifications, sessions, users

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_log = logging.getLogger(__name__)

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY manquante. Définis-la dans l'environnement.")

PURGE_RETENTION_DAYS = int(os.getenv("PURGE_RETENTION_DAYS", "30"))


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


def run_migrations() -> None:
    # 1. Extension vector
    try:
        with _engine.connect() as conn:
            conn.execute(_text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    except Exception as exc:
        _log.error("Extension vector: %s", exc, exc_info=True)

    # 2. Crée les tables manquantes (nouvelles installations)
    try:
        from database import Base
        Base.metadata.create_all(bind=_engine)
    except Exception as exc:
        _log.error("create_all failed: %s", exc, exc_info=True)

    # 3. ALTER TABLE — doit s'exécuter AVANT toute requête ORM sur ces colonnes.
    # backend/db/init-db.sql contient déjà ces colonnes pour les installations neuves ;
    # ce bloc ne sert plus qu'à mettre à niveau une base déjà déployée avant leur ajout
    # (ex: Render en prod, ou un volume Docker local créé avec un ancien init-db.sql).
    try:
        with _engine.connect() as conn:
            conn.execute(_text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS feedback INTEGER"))
            conn.execute(_text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS source_kb_ids INTEGER[]"))
            conn.execute(_text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS transfer_reason VARCHAR(50)"))
            conn.execute(_text("ALTER TABLE utilisateur ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
            conn.execute(_text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))

            # email_verified est nouveau : sur une base déjà déployée (comptes existants
            # créés avant cette fonctionnalité), on ne peut pas leur demander de re-vérifier
            # rétroactivement leur email. On ne "grandfather" (email_verified = true) que la
            # toute première fois où la colonne est ajoutée ; les inscriptions suivantes
            # gardent bien le défaut FALSE et doivent passer par le lien de vérification.
            column_already_existed = conn.execute(_text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'utilisateur' AND column_name = 'email_verified'"
            )).first() is not None
            conn.execute(_text("ALTER TABLE utilisateur ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false"))
            if not column_already_existed:
                conn.execute(_text("UPDATE utilisateur SET email_verified = true"))
                _log.info("email_verified ajoutée : comptes existants marqués comme vérifiés (grandfathering)")

            # tenant_id : préparation multi-tenant (cf. constants.DEFAULT_TENANT_ID). Une
            # seule valeur fixe pour toutes les lignes, sur une base déjà déployée comme sur
            # une neuve — pas de logique de grandfathering nécessaire ici, contrairement à
            # email_verified.
            _default_tenant = "'00000000-0000-0000-0000-000000000001'"
            for _table in ["utilisateur", "chat_sessions", "chat_messages", "ai_call_logs", "knowledge_base", "notifications"]:
                conn.execute(_text(f"ALTER TABLE {_table} ADD COLUMN IF NOT EXISTS tenant_id UUID NOT NULL DEFAULT {_default_tenant}"))
                conn.execute(_text(f"CREATE INDEX IF NOT EXISTS ix_{_table}_tenant_id ON {_table} (tenant_id)"))

            conn.commit()
    except Exception as exc:
        _log.error("ALTER TABLE migration failed: %s", exc, exc_info=True)

    # 4. Rôles + compte admin (les colonnes deleted_at existent maintenant)
    try:
        from database import SessionLocal as _SessionLocal
        from dependencies import pwd_context as _pwd
        with _SessionLocal() as session:
            for role_name in ["user", "ai", "sav", "superviseur", "admin"]:
                if not session.query(models.Role).filter_by(nom_role=role_name).first():
                    session.add(models.Role(nom_role=role_name))
            session.commit()

            admin_role = session.query(models.Role).filter_by(nom_role="admin").first()
            if admin_role:
                admin_email = os.getenv("ADMIN_EMAIL", "admin@smartticket.app")
                admin_username = os.getenv("ADMIN_USERNAME", "admin")
                admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
                # Cherche par email d'abord, puis par username en fallback
                existing_admin = (
                    session.query(models.Utilisateur).filter_by(email=admin_email).first()
                    or session.query(models.Utilisateur).filter_by(username=admin_username).first()
                )
                if existing_admin:
                    existing_admin.email = admin_email
                    existing_admin.username = admin_username
                    existing_admin.password_hash = _pwd.hash(admin_password)
                    existing_admin.id_role = admin_role.id
                    existing_admin.deleted_at = None
                    existing_admin.email_verified = True
                    if not existing_admin.prenom:
                        existing_admin.prenom = "Admin"
                    if not existing_admin.nom:
                        existing_admin.nom = "Admin"
                    session.commit()
                    _log.info("Compte admin synchronisé : %s", admin_email)
                else:
                    session.add(models.Utilisateur(
                        username=admin_username,
                        email=admin_email,
                        password_hash=_pwd.hash(admin_password),
                        id_role=admin_role.id,
                        prenom="Admin",
                        nom="Admin",
                        email_verified=True,
                    ))
                    session.commit()
                    _log.info("Compte admin créé : %s", admin_email)
    except Exception as exc:
        _log.error("Roles/admin setup failed: %s", exc, exc_info=True)


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
        return scheduler
    except Exception as exc:
        _log.error("Scheduler startup failed: %s", exc, exc_info=True)
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()
    scheduler = start_purge_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="CRM Intelligent API",
    description="API pour un gestionnaire de tickets avec intégration IA (Mistral AI + RAG sur pgvector).",
    version="2.6.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "IA", "description": "Endpoints exposant le modèle Mistral AI et le pipeline RAG (Retrieval-Augmented Generation)."},
        {"name": "Base de connaissances", "description": "Indexation et gestion de la base de connaissances vectorielle (pgvector)."},
        {"name": "Sessions", "description": "Gestion des sessions de chat et transferts vers un agent humain."},
        {"name": "Messages", "description": "Lecture, création de messages et feedback utilisateur."},
        {"name": "Authentification", "description": "Inscription, connexion et gestion du profil utilisateur."},
        {"name": "Utilisateurs", "description": "Administration des comptes utilisateurs (admin uniquement)."},
        {"name": "Analytics", "description": "Statistiques et indicateurs de performance du service IA."},
        {"name": "Notifications", "description": "Notifications in-app (réponse SAV, ticket transféré)."},
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

for _router in [auth.router, sessions.router, messages.router, ai.router, knowledge.router, users.router, analytics.router, notifications.router]:
    app.include_router(_router, prefix="/v1")


@app.get("/")
def read_root():
    return {"status": "Online", "message": "Le gestionnaire de tickets avec RAG est prêt"}
