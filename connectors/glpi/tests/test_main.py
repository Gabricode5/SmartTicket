"""API du connecteur : /health et /admin/status."""
from fastapi.testclient import TestClient

from glpi_connector.main import app


def test_health_reports_dry_run_and_defaults():
    client = TestClient(app)
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["dry_run"] is True
    assert body["response_mode"] == "suggested"
    assert body["followup_itemtype"] == "ITILFollowup"
    assert body["followup_is_private"] is True


def test_admin_status_returns_counts(db):
    from glpi_connector import store
    from glpi_connector.db import get_session

    store.record(db, 1, status="dry_run")
    store.record(db, 2, status="dry_run")

    def _override_session():
        yield db

    app.dependency_overrides[get_session] = _override_session
    try:
        body = TestClient(app).get("/admin/status").json()
    finally:
        app.dependency_overrides.clear()
    assert body["dry_run"] is True
    assert body["processed"] == {"dry_run": 2}
