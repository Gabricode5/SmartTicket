"""Tests des endpoints /v1/analytics/stats et /v1/analytics/ai-metrics."""
import os
from datetime import datetime, timedelta

import models


# ---------------------------------------------------------------------------
# Fixture locale : client authentifié comme admin
# ---------------------------------------------------------------------------

def _make_admin_client(client):
    """Crée un compte admin via /setup-admin et retourne un client authentifié."""
    client.post(
        "/v1/setup-admin",
        json={
            "username": "test_admin",
            "email": "admin_test@example.com",
            "password": "admin_password123",
            "prenom": "Admin",
            "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={
        "email": "admin_test@example.com",
        "password": "admin_password123",
    })
    assert resp.status_code == 200, f"Login admin échoué : {resp.json()}"
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAuth:
    """Vérifie le contrôle d'accès sur les deux endpoints analytics."""

    def test_stats_unauthenticated_returns_401(self, client):
        response = client.get("/v1/analytics/stats")
        assert response.status_code == 401

    def test_ai_metrics_unauthenticated_returns_401(self, client):
        response = client.get("/v1/analytics/ai-metrics")
        assert response.status_code == 401

    def test_stats_regular_user_returns_403(self, auth_client):
        """Un utilisateur avec le rôle 'user' ne peut pas accéder aux ."""
        response = auth_client.get("/v1/analytics/stats")
        assert response.status_code == 403

    def test_ai_metrics_regular_user_returns_403(self, auth_client):
        response = auth_client.get("/v1/analytics/ai-metrics")
        assert response.status_code == 403

    def test_stats_pdf_unauthenticated_returns_401(self, client):
        response = client.get("/v1/analytics/stats/pdf")
        assert response.status_code == 401

    def test_ai_metrics_pdf_unauthenticated_returns_401(self, client):
        response = client.get("/v1/analytics/ai-metrics/pdf")
        assert response.status_code == 401

    def test_stats_pdf_regular_user_returns_403(self, auth_client):
        response = auth_client.get("/v1/analytics/stats/pdf")
        assert response.status_code == 403

    def test_ai_metrics_pdf_regular_user_returns_403(self, auth_client):
        response = auth_client.get("/v1/analytics/ai-metrics/pdf")
        assert response.status_code == 403


class TestStats:
    """Vérifie la structure de la réponse /v1/analytics/stats."""

    def test_stats_returns_required_keys(self, client):
        admin_client = _make_admin_client(client)
        response = admin_client.get("/v1/analytics/stats")
        assert response.status_code == 200
        data = response.json()
        expected_keys = [
            "total_sessions",
            "ai_resolution_rate",
            "transferred_count",
            "satisfaction_score",
            "daily_messages",
            "sav_agents",
            "transfer_reasons",
            "alerts",
        ]
        for key in expected_keys:
            assert key in data, f"Clé manquante dans /analytics/stats : '{key}'"

    def test_stats_empty_db_returns_zero_values(self, client):
        """Avec une base vide, les métriques doivent être 0 ou None, pas une erreur."""
        admin_client = _make_admin_client(client)
        response = admin_client.get("/v1/analytics/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 0
        assert data["ai_resolution_rate"] == 0.0
        assert data["transferred_count"] == 0
        assert data["satisfaction_score"] is None


class TestAiMetrics:
    """Vérifie la structure et le calcul de /v1/analytics/ai-metrics."""

    def test_ai_metrics_returns_required_keys(self, client):
        admin_client = _make_admin_client(client)
        response = admin_client.get("/v1/analytics/ai-metrics")
        assert response.status_code == 200
        data = response.json()
        expected_keys = [
            "total_calls",
            "error_rate",
            "avg_latency_ms",
            "avg_rag_chunks",
            "no_context_rate",
            "latency_trend",
            "alerts",
            "kb_score",
        ]
        for key in expected_keys:
            assert key in data, f"Clé manquante dans /analytics/ai-metrics : '{key}'"

    def test_ai_metrics_with_seeded_logs(self, client, db_session):
        """Avec des logs IA en base, les métriques doivent refléter les données."""
        # Seed 5 appels IA réussis (sans id_session — FK nullable)
        base = datetime.utcnow() - timedelta(hours=1)
        for i in range(5):
            db_session.add(models.AICallLog(
                id_session=None,
                call_type="stream",
                model_name="mistral-small-latest",
                latency_ms=2000 + i * 200,
                rag_chunks_found=3 + i,
                rag_context_chars=500,
                success=True,
                date_creation=base + timedelta(minutes=i * 5),
            ))
        # 1 appel en échec
        db_session.add(models.AICallLog(
            id_session=None,
            call_type="stream",
            model_name="mistral-small-latest",
            latency_ms=None,
            rag_chunks_found=0,
            success=False,
            error_type="TimeoutError",
            date_creation=base + timedelta(minutes=30),
        ))
        db_session.commit()

        admin_client = _make_admin_client(client)
        response = admin_client.get("/v1/analytics/ai-metrics")
        assert response.status_code == 200
        data = response.json()

        assert data["total_calls"] == 6
        # 1 échec sur 6 → taux d'erreur ~16.7 %
        assert data["error_rate"] > 0
        # latence moyenne doit être calculée (5 appels réussis)
        assert data["avg_latency_ms"] is not None
        assert data["avg_latency_ms"] > 0


class TestExportPdf:
    """Vérifie les endpoints d'export PDF /v1/analytics/{stats,ai-metrics}/pdf."""

    def test_stats_pdf_returns_valid_pdf(self, client):
        admin_client = _make_admin_client(client)
        response = admin_client.get("/v1/analytics/stats/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content[:4] == b"%PDF"

    def test_ai_metrics_pdf_returns_valid_pdf(self, client):
        admin_client = _make_admin_client(client)
        response = admin_client.get("/v1/analytics/ai-metrics/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content[:4] == b"%PDF"

    def test_stats_pdf_with_seeded_data_returns_valid_pdf(self, client, db_session):
        """Un rapport avec des vraies données (alertes, tableaux non vides) doit rester un PDF valide."""
        admin_client = _make_admin_client(client)
        me = admin_client.get("/v1/me").json()
        session_resp = admin_client.post("/v1/sessions", params={"user_id": me["id"]}, json={"title": "Test export"})
        session_id = session_resp.json()["id"]
        db_session.add(models.ChatMessage(id_session=session_id, type_envoyeur="user", contenu="Bonjour"))
        db_session.add(models.ChatMessage(id_session=session_id, type_envoyeur="ai", contenu="Réponse", feedback=-1))
        db_session.commit()

        response = admin_client.get("/v1/analytics/stats/pdf")
        assert response.status_code == 200
        assert response.content[:4] == b"%PDF"
