"""Tests de GET /v1/me/export (RGPD Art. 15/20) : le PDF doit inclure un
sommaire (nombre de conversations, messages, répartition par statut, période)
en plus du détail complet des conversations."""
import io
import secrets

from pypdf import PdfReader

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_and_get_token(client, mark_verified, email: str, username: str) -> str:
    client.post("/v1/register", json={
        "username": username, "email": email, "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })
    mark_verified(email)
    resp = client.post("/v1/login", json={"email": email, "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() for page in reader.pages)


class TestUserDataExport:
    def test_requires_auth(self, client):
        assert client.get("/v1/me/export").status_code == 401

    def test_export_includes_a_summary_with_status_breakdown(self, client, mark_verified):
        token = _register_and_get_token(client, mark_verified, "export_owner@example.com", "export_owner")
        user_id = client.get("/v1/me", headers=_auth(token)).json()["id"]

        open_session = client.post("/v1/sessions", params={"user_id": user_id}, json={"title": "Question ouverte"}, headers=_auth(token)).json()
        client.post("/v1/messages", json={"id_session": open_session["id"], "type_envoyeur": "user", "contenu": "Bonjour"}, headers=_auth(token))

        closed_session = client.post("/v1/sessions", params={"user_id": user_id}, json={"title": "Question résolue"}, headers=_auth(token)).json()
        client.post(f"/v1/sessions/{closed_session['id']}/close", headers=_auth(token))

        resp = client.get("/v1/me/export", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

        text = _pdf_text(resp.content)
        assert "Resume" in text or "Résumé" in text
        assert "Conversations : 2" in text
        assert "Messages échangés : 1" in text
        # Both statuses represented among the two sessions created above.
        assert "Ouvertes : 1" in text
        assert "Clôturées : 1" in text

    def test_export_with_no_conversations_still_succeeds(self, client, mark_verified):
        token = _register_and_get_token(client, mark_verified, "export_empty@example.com", "export_empty")

        resp = client.get("/v1/me/export", headers=_auth(token))
        assert resp.status_code == 200
        text = _pdf_text(resp.content)
        assert "Conversations : 0" in text
        assert "Aucune conversation." in text
