"""poller.run_once : DRY_RUN strict, filtrage, idempotence, composition du suivi."""
from glpi_connector import store
from glpi_connector.models import ProcessedTicket
from glpi_connector.poller import run_once
from tests._fakes import FakeAnswer, SpyGlpiClient, load_fixture

TICKETS = load_fixture("tickets_list.json")  # ids 12,13 status=1 ; id 14 status=2


def _answer(question):
    assert "<" not in question and ">" not in question  # HTML nettoyé avant le pipeline
    return FakeAnswer(f"Piste de résolution pour : {question[:40]}")


def test_dry_run_never_calls_glpi_write(db):
    spy = SpyGlpiClient(TICKETS, raise_on_write=True)  # toute écriture => AssertionError
    stats = run_once(db, spy, dry_run=True, answer_fn=_answer, statuses=[1])

    assert spy.followups == []                       # AUCUN appel d'écriture
    assert stats.answered == 0
    assert stats.dry_run == 2                        # tickets 12 et 13
    assert len(stats.would_post) == 2
    preview = stats.would_post[0]
    assert preview["itemtype"] == "ITILFollowup"
    assert preview["is_private"] is True
    assert preview["content"].startswith("[Suggestion IA - à valider]")

    rows = db.query(ProcessedTicket).all()
    assert {r.glpi_ticket_id for r in rows} == {12, 13}
    assert {r.status for r in rows} == {"dry_run"}


def test_real_mode_posts_private_followup_with_prefix(db):
    spy = SpyGlpiClient(TICKETS)
    stats = run_once(db, spy, dry_run=False, answer_fn=_answer, statuses=[1])

    assert stats.answered == 2 and stats.dry_run == 0
    assert {f["ticket_id"] for f in spy.followups} == {12, 13}
    assert all(f["is_private"] is True for f in spy.followups)
    assert all(f["content"].startswith("[Suggestion IA - à valider]") for f in spy.followups)
    assert all("assistance d'une IA" in f["content"] for f in spy.followups)

    row = db.get(ProcessedTicket, 12)
    assert row.status == "answered" and row.followup_id == 912  # 900 + id


def test_status_filter_excludes_non_new_tickets(db):
    spy = SpyGlpiClient(TICKETS)
    stats = run_once(db, spy, dry_run=False, answer_fn=_answer, statuses=[1])
    assert stats.seen == 2                       # le ticket 14 (status 2) n'est pas remonté
    assert store.is_processed(db, 14) is False


def test_already_processed_ticket_is_not_reprocessed(db):
    store.record(db, 12, status="answered", followup_id=912)
    spy = SpyGlpiClient(TICKETS)
    stats = run_once(db, spy, dry_run=False, answer_fn=_answer, statuses=[1])

    assert stats.already_processed == 1
    assert stats.answered == 1
    assert {f["ticket_id"] for f in spy.followups} == {13}   # 12 sauté


def test_restart_after_dry_run_does_not_reprocess(db, new_db_session):
    spy1 = SpyGlpiClient(TICKETS, raise_on_write=True)
    run_once(db, spy1, dry_run=True, answer_fn=_answer, statuses=[1])
    db.commit()
    db.close()

    # "redémarrage" : nouvelle session, nouveau client
    fresh = new_db_session()
    spy2 = SpyGlpiClient(TICKETS, raise_on_write=True)
    try:
        stats = run_once(fresh, spy2, dry_run=True, answer_fn=_answer, statuses=[1])
        assert stats.already_processed == 2
        assert stats.dry_run == 0
        assert spy2.followups == []
    finally:
        fresh.close()


def test_empty_ticket_is_skipped(db):
    spy = SpyGlpiClient([{"id": 50, "name": "", "content": "<p>   </p>", "status": 1}])
    stats = run_once(db, spy, dry_run=False, answer_fn=_answer, statuses=[1])
    assert stats.skipped_empty == 1
    assert spy.followups == []
    assert db.get(ProcessedTicket, 50).status == "skipped_empty"


def test_generation_error_is_recorded_without_posting(db):
    def boom(_q):
        raise RuntimeError("pipeline indisponible")

    spy = SpyGlpiClient(TICKETS)
    stats = run_once(db, spy, dry_run=False, answer_fn=boom, statuses=[1])
    assert stats.errors == 2 and stats.answered == 0
    assert spy.followups == []
    assert db.get(ProcessedTicket, 12).status == "error"
