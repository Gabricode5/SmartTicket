"""GET /v1/knowledge-base/ingest-status et /robots-check exigeaient seulement un compte
connecté (get_current_user), contrairement au reste du router knowledge.py qui exige
is_admin_or_sav — un simple compte `user` pouvait donc faire sonder par le backend
n'importe quelle URL externe via robots-check (SSRF-adjacent). Vérifie l'alignement."""
import os
import secrets

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _make_regular_client(client, mark_verified):
    client.post("/v1/register", json={
        "username": "kb_user", "email": "kb_user@example.com",
        "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })
    mark_verified("kb_user@example.com")
    resp = client.post("/v1/login", json={"email": "kb_user@example.com", "password": _TEST_PASSWORD})
    client.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
    return client


def _make_admin_client(client):
    """Même pattern que test_analytics.py::_make_admin_client."""
    client.post(
        "/v1/setup-admin",
        json={
            "username": "kb_admin", "email": "kb_admin@example.com",
            "password": _TEST_PASSWORD, "prenom": "Admin", "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={"email": "kb_admin@example.com", "password": _TEST_PASSWORD})
    client.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
    return client


class TestIngestStatusPermissions:
    def test_regular_user_forbidden(self, client, mark_verified):
        auth_client = _make_regular_client(client, mark_verified)
        resp = auth_client.get("/v1/knowledge-base/ingest-status", params={"job_id": "whatever"})
        assert resp.status_code == 403

    def test_admin_allowed_through(self, client):
        auth_client = _make_admin_client(client)
        # Le rôle passe la vérification ; le job n'existe pas -> 404, pas 403.
        resp = auth_client.get("/v1/knowledge-base/ingest-status", params={"job_id": "unknown-job"})
        assert resp.status_code == 404


class TestRobotsCheckPermissions:
    def test_regular_user_forbidden(self, client, mark_verified):
        auth_client = _make_regular_client(client, mark_verified)
        resp = auth_client.get("/v1/knowledge-base/robots-check", params={"url": "https://example.com"})
        assert resp.status_code == 403

    def test_admin_allowed_through(self, client, monkeypatch):
        import ingest_postgres
        monkeypatch.setattr(
            ingest_postgres, "analyze_robots_and_sitemap",
            lambda base_url: {"allowed": 1, "blocked": 0},
        )
        auth_client = _make_admin_client(client)
        resp = auth_client.get("/v1/knowledge-base/robots-check", params={"url": "https://example.com"})
        assert resp.status_code == 200
