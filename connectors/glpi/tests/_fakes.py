"""Doublures pour les tests du connecteur : aucun réseau, aucune instance GLPI."""
import json
from pathlib import Path

import requests

_FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}
        self.content = b"" if payload is None else json.dumps(payload).encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeGlpiHttp:
    """Transport HTTP branché sur les fixtures JSON. Enregistre chaque requête."""

    def __init__(self, *, list_fixture="tickets_list.json"):
        self.calls: list[dict] = []
        self._list_fixture = list_fixture

    def request(self, method, url, *, headers=None, params=None, json=None, timeout=None):
        self.calls.append(
            {"method": method, "url": url, "headers": headers or {}, "params": params, "json": json}
        )
        path = url.rsplit("/apirest.php", 1)[-1] if "/apirest.php" in url else url

        if url.endswith("/initSession"):
            return FakeResponse(load_fixture("session.json"))
        if url.endswith("/killSession"):
            return FakeResponse({})
        if method == "GET" and path.rstrip("/").endswith("/Ticket/12"):
            return FakeResponse(load_fixture("ticket_12.json"))
        if method == "GET" and (path.rstrip("/").endswith("/Ticket") or "/Ticket?" in url):
            return FakeResponse(load_fixture(self._list_fixture))
        if method == "POST" and path.rstrip("/").endswith(("/ITILFollowup", "/TicketFollowup")):
            return FakeResponse(load_fixture("followup_created.json"), status_code=201)
        return FakeResponse({"error": f"route non mockée: {method} {url}"}, status_code=404)

    # helpers d'assertion
    def writes(self):
        return [c for c in self.calls if c["method"] not in ("GET", "HEAD")]


class FakeAnswer:
    def __init__(self, suggestion, *, chunk_count=1, low_confidence=False):
        self.suggestion = suggestion
        self.chunk_count = chunk_count
        self.low_confidence = low_confidence
        self.model = "fake-generate"


class SpyGlpiClient:
    """Client GLPI factice pour les tests du poller. `raise_on_write=True` fait échouer
    tout appel d'écriture (garde stricte pour le test DRY_RUN)."""

    def __init__(self, tickets, *, raise_on_write=False):
        self._tickets = tickets
        self.raise_on_write = raise_on_write
        self.followups: list[dict] = []
        self.session_opened = 0
        self.session_closed = 0

    def init_session(self):
        self.session_opened += 1
        return "spy-token"

    def kill_session(self):
        self.session_closed += 1

    def __enter__(self):
        self.init_session()
        return self

    def __exit__(self, *_exc):
        self.kill_session()

    def list_tickets(self, *, statuses=None, limit=None):
        rows = list(self._tickets)
        if statuses is not None:
            rows = [t for t in rows if t.get("status") in statuses]
        return rows if limit is None else rows[:limit]

    def get_ticket(self, ticket_id):
        return next(t for t in self._tickets if t["id"] == ticket_id)

    def add_followup(self, ticket_id, content, *, is_private):
        if self.raise_on_write:
            raise AssertionError("add_followup appelé alors qu'aucune écriture n'était attendue")
        self.followups.append(
            {"ticket_id": ticket_id, "content": content, "is_private": is_private}
        )
        return {"id": 900 + ticket_id}
