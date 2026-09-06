"""Configuration rag_core -- lue une seule fois depuis l'environnement (12-factor).

Toutes les valeurs par defaut sont alignees sur backend/dependencies.py / .env.example
pour que rag_core se comporte comme le RAG de Tiqia tant qu'on ne change rien.
"""
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

# --- Base vectorielle dediee -------------------------------------------------------------
# Aucune valeur par defaut : doit etre fournie explicitement (comme DATABASE_URL cote
# Tiqia). Le controle "manquante" est fait a la construction de l'engine (rag_core/db.py),
# pas ici, pour que les modules purs (prompt, catalogue) restent importables sans base.
RAG_DATABASE_URL = os.getenv("RAG_DATABASE_URL")

# Mono-tenant STRICT (1 installation = 1 client, on-premise). tenant_id est neanmoins pose
# sur la table -- valeur fixe, jamais filtree en requete -- pour une parite de schema avec
# Tiqia (cf. backend/constants.py::DEFAULT_TENANT_ID) : une eventuelle fusion de donnees
# reste une fusion, pas une reecriture de schema.
TENANT_ID = uuid.UUID(os.getenv("RAG_TENANT_ID", "00000000-0000-0000-0000-000000000001"))

# --- Modeles ---------------------------------------------------------------------------
# None => la factory (rag_core/llm/factory.py) retombe sur le defaut du catalogue ferme.
# Toute valeur non vide est validee contre le catalogue (nom inconnu => UnknownModelError).
GENERATION_MODEL = os.getenv("RAG_GENERATION_MODEL") or None
EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL") or None
# Dimension du vecteur stocke (colonne pgvector). Doit correspondre a la dimension du
# modele d'embedding du catalogue -- verifie a la construction de l'Embedder.
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
REQUEST_TIMEOUT = float(os.getenv("RAG_REQUEST_TIMEOUT", "30"))

# --- Retrieval + reranking (memes defauts que backend/) --------------------------------
KB_TOP_K = int(os.getenv("KB_TOP_K", "4"))
KB_MAX_CONTEXT_CHARS = int(os.getenv("KB_MAX_CONTEXT_CHARS", "3000"))
RERANK_FETCH_MULTIPLIER = int(os.getenv("RERANK_FETCH_MULTIPLIER", "3"))
RERANK_LEXICAL_WEIGHT = float(os.getenv("RERANK_LEXICAL_WEIGHT", "0.3"))
RERANK_FEEDBACK_WEIGHT = float(os.getenv("RERANK_FEEDBACK_WEIGHT", "0.2"))
RERANK_QUARANTINE_THRESHOLD = int(os.getenv("RERANK_QUARANTINE_THRESHOLD", "-3"))

# Distance cosinus au-dela de laquelle le meilleur chunk est juge non pertinent -- sert a
# poser un drapeau "low_confidence" sur le resultat (la passerelle pourra decider de ne
# pas suggerer, ou de suggerer avec un avertissement). Point de depart, non calibre.
RAG_LOW_CONFIDENCE_DISTANCE = float(os.getenv("RAG_LOW_CONFIDENCE_DISTANCE", "0.4"))

# --- Prompt : surcouche client (couche 2) ---------------------------------------------
# Personnalisation par installation (ton, langue, formules, perimetre). NE PEUT JAMAIS
# ecraser les garde-fous de la couche 1 -- cf. rag_core/prompt.py pour l'ordre impose et
# la sanitisation. Vide par defaut = comportement generique.
CLIENT_PROMPT_OVERLAY = os.getenv("RAG_CLIENT_PROMPT_OVERLAY", "").strip()

# --- Fournisseur Mistral (seule implementation LLMProvider pour l'instant) --------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1").rstrip("/")
MISTRAL_MAX_RETRIES = int(os.getenv("MISTRAL_MAX_RETRIES", "5"))
MISTRAL_BACKOFF_SECONDS = float(os.getenv("MISTRAL_BACKOFF_SECONDS", "2"))
