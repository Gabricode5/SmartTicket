"""Le worker : ouvre/ferme UNE session GLPI et boucle run_once sans dormir en trop."""
from glpi_connector import worker
from tests._fakes import SpyGlpiClient, load_fixture


def test_run_forever_loops_bounded_and_manages_session(monkeypatch):
    spy = SpyGlpiClient(load_fixture("tickets_list.json"))
    monkeypatch.setattr(worker, "GlpiClient", lambda *a, **k: spy)

    calls = []
    monkeypatch.setattr(worker, "run_once", lambda db, client, **kw: calls.append(client))

    class _FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(worker, "SessionLocal", lambda: _FakeSession())

    slept = []
    worker.run_forever(_max_iterations=3, _sleep=slept.append)

    assert len(calls) == 3                    # run_once appelé à chaque itération
    assert all(c is spy for c in calls)
    assert spy.session_opened == 1            # une seule session pour toute la boucle
    assert spy.session_closed == 1
    assert slept == [worker.config.POLL_INTERVAL_SECONDS] * 2  # pas de sleep après la dernière
