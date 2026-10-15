"""Idempotence : un ticket traité n'est jamais retraité, y compris après redémarrage."""
from sqlalchemy import func, select

from glpi_connector import store
from glpi_connector.models import ProcessedTicket


def _rows(db) -> int:
    return db.execute(select(func.count()).select_from(ProcessedTicket)).scalar_one()


def test_is_processed_lifecycle(db):
    assert store.is_processed(db, 12) is False
    store.record(db, 12, status="answered", followup_id=990, suggestion_chars=120)
    assert store.is_processed(db, 12) is True

    row = db.get(ProcessedTicket, 12)
    assert row.status == "answered"
    assert row.followup_id == 990
    assert row.suggestion_chars == 120
    assert row.processed_at is not None


def test_record_is_idempotent_no_duplicate_row(db):
    store.record(db, 12, status="dry_run", suggestion_chars=10)
    store.record(db, 12, status="answered", followup_id=5, suggestion_chars=42)
    assert _rows(db) == 1
    row = db.get(ProcessedTicket, 12)
    assert row.status == "answered" and row.followup_id == 5


def test_processed_state_survives_worker_restart(db, new_db_session):
    store.record(db, 77, status="answered")
    db.close()

    # "redémarrage du worker" : nouvelle session sur la même base
    fresh = new_db_session()
    try:
        assert store.is_processed(fresh, 77) is True
        assert store.is_processed(fresh, 78) is False
    finally:
        fresh.close()


def test_counts_by_status(db):
    store.record(db, 1, status="answered")
    store.record(db, 2, status="answered")
    store.record(db, 3, status="dry_run")
    store.record(db, 4, status="error", detail="boom")
    assert store.counts_by_status(db) == {"answered": 2, "dry_run": 1, "error": 1}
