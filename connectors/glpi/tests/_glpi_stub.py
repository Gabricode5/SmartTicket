"""Stub GLPI servi par un vrai serveur HTTP local (http.server), pour un bout-en-bout
sur le VRAI GlpiClient : vraies requêtes `requests` sur TCP, vrai cycle de session, vrai
round-trip JSON, vrai raise_for_status. Seules les entrailles de GLPI sont simulées.

Implémente le sous-ensemble utilisé par le connecteur :
  GET  /initSession        (App-Token + Authorization: user_token -> session_token)
  GET  /killSession        (Session-Token -> {})
  GET  /Ticket             (liste)
  GET  /Ticket/{id}
  POST /ITILFollowup       ({"input": {...}} -> {"id": N, ...})
"""
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


class _State:
    def __init__(self):
        self.sessions: set[str] = set()
        self.tickets: dict[int, dict] = {}
        self.followups: list[dict] = []
        self._next_followup_id = 1

    def add_followup(self, payload: dict) -> int:
        fid = self._next_followup_id
        self._next_followup_id += 1
        self.followups.append({"id": fid, **payload})
        return fid


def _make_handler(state: _State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a):  # silence
            pass

        def _send(self, code: int, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _session_ok(self) -> bool:
            return self.headers.get("Session-Token") in state.sessions

        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path.rstrip("/")
            if path.endswith("/initSession"):
                if not self.headers.get("App-Token"):
                    return self._send(401, {"error": "App-Token manquant"})
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("user_token "):
                    return self._send(401, {"error": "user_token manquant"})
                token = uuid.uuid4().hex
                state.sessions.add(token)
                return self._send(200, {"session_token": token})

            if path.endswith("/killSession"):
                state.sessions.discard(self.headers.get("Session-Token", ""))
                return self._send(200, {})

            if not self._session_ok():
                return self._send(401, {"error": "Session-Token invalide"})

            segs = [s for s in path.split("/") if s]
            if len(segs) >= 2 and segs[-2] == "Ticket":
                ticket = state.tickets.get(int(segs[-1]))
                return self._send(200 if ticket else 404, ticket or {"error": "not found"})
            if segs and segs[-1] == "Ticket":
                return self._send(200, list(state.tickets.values()))
            return self._send(404, {"error": f"route inconnue: {path}"})

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path.rstrip("/")
            if not self._session_ok():
                return self._send(401, {"error": "Session-Token invalide"})
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            if path.endswith(("/ITILFollowup", "/TicketFollowup")):
                fid = state.add_followup(dict(body.get("input", {})))
                return self._send(201, {"id": fid, "message": "Item successfully added"})
            return self._send(404, {"error": f"route inconnue: {path}"})

    return Handler


class GlpiStub:
    def __init__(self):
        self.state = _State()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self.state))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def followups(self) -> list[dict]:
        return self.state.followups

    @property
    def sessions(self) -> set[str]:
        return self.state.sessions

    def seed_ticket(self, ticket_id: int, name: str, content: str, *, status: int = 1):
        self.state.tickets[ticket_id] = {
            "id": ticket_id, "name": name, "content": content, "status": status
        }

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
