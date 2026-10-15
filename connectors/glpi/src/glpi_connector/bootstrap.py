"""Initialisation idempotente du schéma (pgvector + état du connecteur).

Appelé au démarrage de main.py (web) ET worker.py : CREATE EXTENSION vector, puis
Base.metadata.create_all() pour les deux schémas (knowledge_chunk, processed_tickets).
Idempotent (IF NOT EXISTS / create_all ne recrée jamais une table existante) donc sans
risque d'être appelé par les deux entrées de la même image, y compris en parallèle.

Retry : au tout premier démarrage du compose, pgvector peut ne pas encore accepter de
connexions (healthcheck pas encore passé) -- on retente avec un backoff court plutôt que
de planter immédiatement.
"""
import logging
import time
from typing import Callable

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

_MAX_RETRIES = 10
_RETRY_DELAY_SECONDS = 3.0


def _retry(fn: Callable[[], None], *, what: str) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            fn()
            return
        except OperationalError as exc:
            last_exc = exc
            logger.warning(
                "%s : base pas encore prête (tentative %d/%d) -- nouvel essai dans %.0fs",
                what, attempt, _MAX_RETRIES, _RETRY_DELAY_SECONDS,
            )
            time.sleep(_RETRY_DELAY_SECONDS)
    raise RuntimeError(f"{what} : base injoignable après {_MAX_RETRIES} tentatives") from last_exc


def init_schema() -> None:
    import rag_core.models  # noqa: F401  (enregistre KnowledgeChunk sur Base)
    from rag_core.db import Base as RagBase
    from rag_core.db import engine as rag_engine

    import glpi_connector.models  # noqa: F401  (enregistre ProcessedTicket sur Base)
    from glpi_connector.db import Base as ConnectorBase
    from glpi_connector.db import engine as connector_engine

    def _create_extension() -> None:
        with rag_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    def _create_tables() -> None:
        RagBase.metadata.create_all(rag_engine)
        ConnectorBase.metadata.create_all(connector_engine)

    logger.info("Initialisation du schéma (CREATE EXTENSION vector + create_all)...")
    _retry(_create_extension, what="CREATE EXTENSION vector")
    _retry(_create_tables, what="create_all (knowledge_chunk, processed_tickets)")
    logger.info("Schéma prêt.")
