"""Tests des endpoints /v1/analytics/stats, /v1/analytics/ai-metrics et
/v1/analytics/knowledge-gaps."""
import os
import secrets
from datetime import datetime, timedelta

import models

_TEST_PASSWORD = secrets.token_urlsafe(16)


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
            "password": _TEST_PASSWORD,
            "prenom": "Admin",
            "nom": "Test",
        },
        headers={"X-Setup-Key": os.environ["ADMIN_SETUP_KEY"]},
    )
    resp = client.post("/v1/login", json={
        "email": "admin_test@example.com",
        "password": _TEST_PASSWORD,
    })
    assert resp.status_code == 200, f"Login admin échoué : {resp.json()}"
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _make_sav_client(client, mark_verified, role: str = "sav"):
    """Crée un compte user, le promeut sav/superviseur via un admin temporaire, et
    authentifie `client` en tant que ce compte -- pour vérifier que knowledge-gaps est bien
    plus strict que is_admin_or_sav (qui laisse passer sav/superviseur ailleurs)."""
    client.post("/v1/register", json={
        "username": f"gaps_{role}", "email": f"gaps_{role}@example.com",
        "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
    })
    mark_verified(f"gaps_{role}@example.com")
    login = client.post("/v1/login", json={"email": f"gaps_{role}@example.com", "password": _TEST_PASSWORD})
    token = login.json()["access_token"]
    user_id = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

    admin_client = _make_admin_client(client)  # mute client.headers vers l'admin temporaire
    promote = admin_client.put(f"/v1/users/{user_id}/role", json={"role": role})
    assert promote.status_code == 200, promote.json()

    client.headers.update({"Authorization": f"Bearer {token}"})  # bascule sur le compte promu
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


# ---------------------------------------------------------------------------
# /v1/analytics/knowledge-gaps
# ---------------------------------------------------------------------------

def _seed_question_and_call(db_session, session_id, question_text, *, rag_chunks_found, best_match_distance, when=None):
    """flush() (pas juste commit()) pour récupérer message.id sans déclencher un rechargement
    lazy sur un objet expiré par le commit -- nécessaire pour question_message_id."""
    message = models.ChatMessage(id_session=session_id, type_envoyeur="user", contenu=question_text)
    db_session.add(message)
    db_session.flush()
    call = models.AICallLog(
        id_session=session_id, call_type="stream", model_name="mistral-small-latest",
        latency_ms=1000, rag_chunks_found=rag_chunks_found, rag_context_chars=100,
        best_match_distance=best_match_distance, question_message_id=message.id,
        success=True, date_creation=when or datetime.utcnow(),
    )
    db_session.add(call)
    db_session.commit()
    return message, call


class TestKnowledgeGaps:
    """Vérifie /v1/analytics/knowledge-gaps : accès admin STRICT (plus restrictif que
    is_admin_or_sav utilisé partout ailleurs) et le regroupement V1 des questions sans bonne
    réponse (quasi-doublon de texte normalisé, pas un vrai clustering sémantique)."""

    def test_unauthenticated_returns_401(self, client):
        response = client.get("/v1/analytics/knowledge-gaps")
        assert response.status_code == 401

    def test_regular_user_returns_403(self, auth_client):
        response = auth_client.get("/v1/analytics/knowledge-gaps")
        assert response.status_code == 403

    def test_sav_returns_403(self, client, mark_verified):
        """Contrairement à /stats et /ai-metrics (is_admin_or_sav), sav n'a PAS accès ici --
        décision validée le 2026-08-19 : questions brutes potentiellement personnelles."""
        sav_client = _make_sav_client(client, mark_verified, role="sav")
        response = sav_client.get("/v1/analytics/knowledge-gaps")
        assert response.status_code == 403

    def test_superviseur_returns_403(self, client, mark_verified):
        supervisor_client = _make_sav_client(client, mark_verified, role="superviseur")
        response = supervisor_client.get("/v1/analytics/knowledge-gaps")
        assert response.status_code == 403

    def test_admin_empty_db_returns_empty_list(self, client):
        admin_client = _make_admin_client(client)
        response = admin_client.get("/v1/analytics/knowledge-gaps")
        assert response.status_code == 200
        data = response.json()
        assert data == {"gaps": [], "total_gap_calls": 0, "total_distinct_gaps": 0}

    def test_groups_identical_questions_ignoring_case_and_whitespace(self, client, db_session):
        admin_client = _make_admin_client(client)
        me = admin_client.get("/v1/me").json()
        session_id = admin_client.post("/v1/sessions", params={"user_id": me["id"]}, json={"title": "T"}).json()["id"]

        _seed_question_and_call(db_session, session_id, "Comment configurer mon compte ?", rag_chunks_found=0, best_match_distance=None)
        _seed_question_and_call(db_session, session_id, "  comment CONFIGURER mon compte ?  ", rag_chunks_found=0, best_match_distance=None)

        response = admin_client.get("/v1/analytics/knowledge-gaps")
        assert response.status_code == 200
        data = response.json()
        assert data["total_gap_calls"] == 2
        assert data["total_distinct_gaps"] == 1
        assert data["gaps"][0]["occurrences"] == 2
        # Le texte affiché est celui de l'occurrence traitée en premier (tri par date
        # décroissante -> la plus RÉCENTE des deux), pas forcément la 1re saisie -- seule la
        # casse/les espaces varient entre les deux, donc une comparaison insensible à la casse
        # suffit à vérifier qu'aucune des deux n'a été perdue.
        assert data["gaps"][0]["question"].strip().lower() == "comment configurer mon compte ?"

    def test_flags_high_distance_even_when_chunks_were_found(self, client, db_session):
        """rag_chunks_found > 0 ne suffit pas : le reranking ne rejette jamais par distance
        (cf. rag_reranking.py), donc un best_match_distance élevé doit être détecté ici."""
        admin_client = _make_admin_client(client)
        me = admin_client.get("/v1/me").json()
        session_id = admin_client.post("/v1/sessions", params={"user_id": me["id"]}, json={"title": "T"}).json()["id"]

        _seed_question_and_call(db_session, session_id, "Question hors sujet totalement", rag_chunks_found=3, best_match_distance=0.9)

        response = admin_client.get("/v1/analytics/knowledge-gaps")
        data = response.json()
        assert data["total_distinct_gaps"] == 1
        assert data["gaps"][0]["question"] == "Question hors sujet totalement"

    def test_excludes_calls_with_a_good_match(self, client, db_session):
        admin_client = _make_admin_client(client)
        me = admin_client.get("/v1/me").json()
        session_id = admin_client.post("/v1/sessions", params={"user_id": me["id"]}, json={"title": "T"}).json()["id"]

        _seed_question_and_call(db_session, session_id, "Comment réinitialiser mon mot de passe ?", rag_chunks_found=3, best_match_distance=0.05)

        response = admin_client.get("/v1/analytics/knowledge-gaps")
        data = response.json()
        assert data["total_distinct_gaps"] == 0

    def test_sorted_by_occurrence_descending(self, client, db_session):
        admin_client = _make_admin_client(client)
        me = admin_client.get("/v1/me").json()
        session_id = admin_client.post("/v1/sessions", params={"user_id": me["id"]}, json={"title": "T"}).json()["id"]

        _seed_question_and_call(db_session, session_id, "Question rare", rag_chunks_found=0, best_match_distance=None)
        _seed_question_and_call(db_session, session_id, "Question fréquente", rag_chunks_found=0, best_match_distance=None)
        _seed_question_and_call(db_session, session_id, "Question fréquente", rag_chunks_found=0, best_match_distance=None)

        response = admin_client.get("/v1/analytics/knowledge-gaps")
        data = response.json()
        assert data["gaps"][0]["question"] == "Question fréquente"
        assert data["gaps"][0]["occurrences"] == 2
        assert data["gaps"][1]["question"] == "Question rare"
        assert data["gaps"][1]["occurrences"] == 1
