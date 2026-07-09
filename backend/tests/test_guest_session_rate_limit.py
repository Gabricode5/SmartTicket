"""Vérifie que POST /v1/sessions/guest est bien rate-limité (chat anonyme public, même
risque d'abus que POST /v1/register — cf. test_register_rate_limit.py)."""


class TestGuestSessionRateLimit:
    def test_exceeding_the_limit_returns_429(self, client, monkeypatch):
        # Même technique que test_register_rate_limit.py : la limite globale est
        # désactivée dans conftest.py, on la restaure ici via l'attribut du module que le
        # decorator callable (`lambda: GUEST_SESSION_RATE_LIMIT`) relit à chaque requête.
        import routers.sessions as sessions_module
        monkeypatch.setattr(sessions_module, "GUEST_SESSION_RATE_LIMIT", "2/hour")

        assert client.post("/v1/sessions/guest").status_code == 200
        assert client.post("/v1/sessions/guest").status_code == 200
        assert client.post("/v1/sessions/guest").status_code == 429
