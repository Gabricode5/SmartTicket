"""Configuration du connecteur GLPI -- lue depuis l'environnement.

Defaults PRUDENTS (décision étape 3), en config jamais en dur :
  GLPI 10.x, ITILFollowup, is_private=true, préfixe "[Suggestion IA - à valider]",
  DRY_RUN=true (strict), RESPONSE_MODE=suggested (seul mode autorisé).
"""
import os

from dotenv import load_dotenv
from rag_core.prompt import AI_ASSISTANCE_DISCLOSURE_FR

load_dotenv()


def _int_list(raw: str) -> list[int]:
    return [int(x) for x in raw.replace(";", ",").split(",") if x.strip()]


# --- Accès API GLPI -------------------------------------------------------------------
GLPI_URL = os.getenv("GLPI_URL", "").rstrip("/")          # ex: https://glpi.client.local/apirest.php
GLPI_APP_TOKEN = os.getenv("GLPI_APP_TOKEN", "")
GLPI_USER_TOKEN = os.getenv("GLPI_USER_TOKEN", "")
GLPI_API_VERSION = os.getenv("GLPI_API_VERSION", "10")    # 10.x par défaut
GLPI_HTTP_TIMEOUT = float(os.getenv("GLPI_HTTP_TIMEOUT", "20"))

# --- Sélection des tickets à traiter ------------------------------------------------
# Statuts GLPI : 1=nouveau, 2=en cours (attribué), 3=en cours (planifié), 4=en attente,
# 5=résolu, 6=clos. Défaut prudent : uniquement les nouveaux.
GLPI_TICKET_STATUS_FILTER = _int_list(os.getenv("GLPI_TICKET_STATUS_FILTER", "1"))
GLPI_LIST_LIMIT = int(os.getenv("GLPI_LIST_LIMIT", "50"))

# --- Écriture du suivi -------------------------------------------------------------
# ITILFollowup en GLPI 10 ; une instance GLPI 9.5 mettrait "TicketFollowup".
GLPI_FOLLOWUP_ITEMTYPE = os.getenv("GLPI_FOLLOWUP_ITEMTYPE", "ITILFollowup")
# Suivi PRIVÉ par défaut : visible des agents, invisible du demandeur.
FOLLOWUP_IS_PRIVATE = os.getenv("FOLLOWUP_IS_PRIVATE", "true").lower() != "false"
SUGGESTION_PREFIX = os.getenv("SUGGESTION_PREFIX", "[Suggestion IA - à valider]")

# --- Comportement du poller -------------------------------------------------------
# STRICT : seule la valeur littérale "false" (insensible à la casse) désarme le dry-run.
# Toute autre valeur (vide, "0", faute de frappe...) => on reste en dry-run.
DRY_RUN = os.getenv("DRY_RUN", "true").strip().lower() != "false"

# Seul mode supporté : l'IA ne répond jamais en autonomie. Toute autre valeur = erreur.
RESPONSE_MODE = os.getenv("RESPONSE_MODE", "suggested").strip().lower()
if RESPONSE_MODE != "suggested":
    raise RuntimeError(
        f"RESPONSE_MODE={RESPONSE_MODE!r} non supporté. Seul 'suggested' est autorisé "
        "(l'IA ne répond jamais directement au client)."
    )

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

# Mention AI Act (art. 50) apposée à la suggestion, jointe au texte que l'agent relaie au
# client (cf. poller._compose_followup). Source unique de vérité = rag_core.prompt, pour
# ne pas dupliquer ce texte entre les deux packages. Vide = aucune (override par le client
# via AI_DISCLOSURE, ex. traduction ou formulation propre à l'installation).
AI_DISCLOSURE = os.getenv("AI_DISCLOSURE", AI_ASSISTANCE_DISCLOSURE_FR)

# --- Base d'état du connecteur (processed_tickets) -------------------------------
# Distincte de la base vectorielle rag_core (RAG_DATABASE_URL) et de celle de Tiqia.
CONNECTOR_DATABASE_URL = os.getenv("CONNECTOR_DATABASE_URL")

# Mono-tenant strict (1 installation = 1 client GLPI).
CONNECTOR_TENANT_ID = os.getenv(
    "CONNECTOR_TENANT_ID", "00000000-0000-0000-0000-000000000001"
)

# Surcouche prompt client transmise à rag_core (facultative).
CLIENT_PROMPT_OVERLAY = os.getenv("RAG_CLIENT_PROMPT_OVERLAY", "").strip() or None
