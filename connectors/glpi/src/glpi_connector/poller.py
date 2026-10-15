"""Boucle de traitement : tickets GLPI -> suggestion rag_core -> suivi ITILFollowup.

`run_once` fait UN passage. En DRY_RUN (défaut, strict) il LOGUE ce qu'il posterait et
n'émet AUCUN appel d'écriture GLPI. `answer_fn` et le client sont injectables pour les
tests (aucune instance GLPI ni base vectorielle requise).
"""
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from glpi_connector import config, store
from glpi_connector.glpi_client import GlpiClient

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class PollStats:
    seen: int = 0
    already_processed: int = 0
    answered: int = 0
    dry_run: int = 0
    skipped_empty: int = 0
    errors: int = 0
    would_post: list[dict] = field(default_factory=list)  # aperçu des suivis en dry-run


def _plain_text(ticket: dict) -> str:
    raw = ticket.get("content") or ""
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", raw)).strip()
    return text or (ticket.get("name") or "").strip()


def _compose_followup(suggestion: str) -> str:
    parts = [config.SUGGESTION_PREFIX, "", suggestion.strip()]
    if config.AI_DISCLOSURE:
        parts += ["", config.AI_DISCLOSURE]
    return "\n".join(parts).strip()


def _default_answer_fn():
    """Fabrique l'answer_fn de production : ouvre une session rag_core et appelle le
    pipeline. Import différé pour que le connecteur reste importable sans base vectorielle."""
    from rag_core.db import SessionLocal as RagSession
    from rag_core.pipeline import answer as rag_answer

    def answer_fn(question: str):
        with RagSession() as rag_db:
            return rag_answer(rag_db, question, client_overlay=config.CLIENT_PROMPT_OVERLAY)

    return answer_fn


def run_once(
    db: Session,
    client: GlpiClient,
    *,
    dry_run: bool | None = None,
    answer_fn=None,
    statuses: list[int] | None = None,
    limit: int | None = None,
) -> PollStats:
    dry_run = config.DRY_RUN if dry_run is None else dry_run
    answer_fn = answer_fn or _default_answer_fn()
    statuses = statuses if statuses is not None else config.GLPI_TICKET_STATUS_FILTER

    stats = PollStats()
    tickets = client.list_tickets(statuses=statuses, limit=limit)
    for ticket in tickets:
        stats.seen += 1
        tid = ticket["id"]

        if store.is_processed(db, tid):
            stats.already_processed += 1
            continue

        question = _plain_text(ticket)
        if not question:
            store.record(db, tid, status="skipped_empty")
            stats.skipped_empty += 1
            continue

        try:
            result = answer_fn(question)
            body = _compose_followup(result.suggestion)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ticket %s : échec génération de la suggestion", tid)
            store.record(db, tid, status="error", detail=str(exc))
            stats.errors += 1
            continue

        if dry_run:
            preview = {
                "ticket_id": tid,
                "itemtype": config.GLPI_FOLLOWUP_ITEMTYPE,
                "is_private": config.FOLLOWUP_IS_PRIVATE,
                "content": body,
            }
            logger.info(
                "[DRY_RUN] ticket %s -> %s (is_private=%s), %d caractères — AUCUN appel GLPI.\n%s",
                tid, preview["itemtype"], preview["is_private"], len(body), body,
            )
            stats.would_post.append(preview)
            store.record(db, tid, status="dry_run", suggestion_chars=len(result.suggestion))
            stats.dry_run += 1
            continue

        created = client.add_followup(tid, body, is_private=config.FOLLOWUP_IS_PRIVATE)
        store.record(
            db,
            tid,
            status="answered",
            followup_id=created.get("id"),
            suggestion_chars=len(result.suggestion),
        )
        stats.answered += 1

    logger.info(
        "Passage terminé : vus=%d déjà=%d répondus=%d dry_run=%d vides=%d erreurs=%d",
        stats.seen, stats.already_processed, stats.answered, stats.dry_run,
        stats.skipped_empty, stats.errors,
    )
    return stats
