"""Tests de l'endpoint GET /v1/sessions/search (full-text)."""
import secrets

import models

# Généré aléatoirement à chaque run (jamais une chaîne en dur) pour créer des comptes
# jetables dans la base de test locale/CI (conftest.py refuse de démarrer si
# TEST_DATABASE_URL ne contient pas "test" — ces comptes ne peuvent jamais exister ailleurs).
_TEST_PASSWORD = secrets.token_urlsafe(16)


def _create_session_with_message(auth_client, db_session, user_id: int, title: str, contenu: str) -> int:
    resp = auth_client.post("/v1/sessions", params={"user_id": user_id}, json={"title": title})
    assert resp.status_code == 200
    session_id = resp.json()["id"]
    db_session.add(models.ChatMessage(id_session=session_id, type_envoyeur="user", contenu=contenu))
    db_session.commit()
    return session_id


class TestSessionSearch:
    def test_requires_auth(self, client):
        resp = client.get("/v1/sessions/search", params={"user_id": 1, "q": "test"})
        assert resp.status_code == 401

    def test_empty_query_returns_empty_list(self, auth_client):
        me = auth_client.get("/v1/me").json()
        resp = auth_client.get("/v1/sessions/search", params={"user_id": me["id"], "q": "   "})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_finds_session_by_message_content(self, auth_client, db_session):
        me = auth_client.get("/v1/me").json()
        matching_id = _create_session_with_message(
            auth_client, db_session, me["id"], "Souci technique",
            "Bonjour, je n'arrive pas à réinitialiser mon mot de passe depuis hier.",
        )
        _create_session_with_message(
            auth_client, db_session, me["id"], "Autre sujet",
            "Question sans rapport concernant la facturation mensuelle.",
        )

        resp = auth_client.get("/v1/sessions/search", params={"user_id": me["id"], "q": "réinitialiser"})
        assert resp.status_code == 200
        results = resp.json()
        ids = [r["id"] for r in results]
        assert matching_id in ids
        assert len(results) == 1
        matched = next(r for r in results if r["id"] == matching_id)
        assert matched["snippet"] is not None
        assert "<b>" in matched["snippet"]

    def test_finds_session_by_title_without_message_match(self, auth_client, db_session):
        me = auth_client.get("/v1/me").json()
        session_id = _create_session_with_message(
            auth_client, db_session, me["id"], "Problème de facturation urgent",
            "Contenu générique qui ne contient pas le mot recherché.",
        )

        resp = auth_client.get("/v1/sessions/search", params={"user_id": me["id"], "q": "facturation"})
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert session_id in ids

    def test_no_match_returns_empty_list(self, auth_client, db_session):
        me = auth_client.get("/v1/me").json()
        _create_session_with_message(
            auth_client, db_session, me["id"], "Titre neutre",
            "Un message qui ne contient aucun terme pertinent.",
        )

        resp = auth_client.get("/v1/sessions/search", params={"user_id": me["id"], "q": "motintrouvable"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_cannot_search_other_users_sessions(self, client):
        client.post("/v1/register", json={
            "username": "search_user_a", "email": "search_a@example.com",
            "password": _TEST_PASSWORD, "prenom": "A", "nom": "A",
        })
        client.post("/v1/register", json={
            "username": "search_user_b", "email": "search_b@example.com",
            "password": _TEST_PASSWORD, "prenom": "B", "nom": "B",
        })
        token_a = client.post("/v1/login", json={"email": "search_a@example.com", "password": _TEST_PASSWORD}).json()["access_token"]
        user_b_id = client.post("/v1/login", json={"email": "search_b@example.com", "password": _TEST_PASSWORD}).json()["user_id"]

        resp = client.get(
            "/v1/sessions/search",
            params={"user_id": user_b_id, "q": "test"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 403
