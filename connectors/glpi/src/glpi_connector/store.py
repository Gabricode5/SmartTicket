"""Idempotence du poller : registre des tickets GLPI déjà traités.

`is_processed` est la garde appelée AVANT tout traitement d'un ticket ; `record` inscrit
le résultat. L'état vit en base -> un redémarrage du worker ne provoque aucun retraitement.
"""
from sqlalchemy.orm import Session

from glpi_connector.models import ProcessedTicket


def is_processed(db: Session, glpi_ticket_id: int) -> bool:
    return (
        db.query(ProcessedTicket.glpi_ticket_id)
        .filter(ProcessedTicket.glpi_ticket_id == glpi_ticket_id)
        .first()
        is not None
    )


def record(
    db: Session,
    glpi_ticket_id: int,
    *,
    status: str,
    followup_id: int | None = None,
    suggestion_chars: int | None = None,
    detail: str | None = None,
) -> ProcessedTicket:
    """Inscrit (ou met à jour) le résultat de traitement d'un ticket. Idempotent :
    ré-appeler pour un ticket déjà présent met simplement à jour la ligne."""
    row = db.get(ProcessedTicket, glpi_ticket_id)
    if row is None:
        row = ProcessedTicket(glpi_ticket_id=glpi_ticket_id)
        db.add(row)
    row.status = status
    row.followup_id = followup_id
    row.suggestion_chars = suggestion_chars
    row.detail = detail
    db.commit()
    return row


def counts_by_status(db: Session) -> dict[str, int]:
    from sqlalchemy import func

    rows = (
        db.query(ProcessedTicket.status, func.count(ProcessedTicket.glpi_ticket_id))
        .group_by(ProcessedTicket.status)
        .all()
    )
    return {status: n for status, n in rows}
