import logging
import os

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

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY manquante. Définis-la dans l'environnement.")

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


@app.on_event("startup")
def run_migrations():
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
    with _engine.connect() as conn:
        conn.execute(_text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS feedback INTEGER"))
        conn.execute(_text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS transfer_reason VARCHAR(50)"))
        conn.commit()


@app.get("/")
def read_root():
    return {"status": "Online", "message": "Le gestionnaire de tickets avec RAG est prêt"}
