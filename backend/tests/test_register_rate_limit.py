"""Vérifie que POST /v1/register est bien rate-limité (porte ouverte au spam de comptes
jetables en inscription publique sinon, cf. contexte B2B2C)."""
import secrets

_TEST_PASSWORD = secrets.token_urlsafe(16)


class TestRegisterRateLimit:
    def test_exceeding_the_limit_returns_429(self, client, monkeypatch):
        # La limite réelle est désactivée globalement dans conftest.py (10000/minute) pour
        # que le reste de la suite puisse s'inscrire librement — on la restaure ici, pour ce
        # seul test, en patchant l'attribut du module : le decorator sur /register est un
        # callable (`lambda: REGISTER_RATE_LIMIT`), relu par slowapi à chaque requête plutôt
        # que figé au chargement du module, donc ce monkeypatch a bien un effet réel.
        import routers.auth as auth_module
        monkeypatch.setattr(auth_module, "REGISTER_RATE_LIMIT", "2/hour")

        def _register(n: int):
            return client.post("/v1/register", json={
                "username": f"rl_user_{n}", "email": f"rl_user_{n}@example.com",
                "password": _TEST_PASSWORD, "prenom": "P", "nom": "N",
            })

        assert _register(1).status_code == 201
        assert _register(2).status_code == 201
        assert _register(3).status_code == 429
