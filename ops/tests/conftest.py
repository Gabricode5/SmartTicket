import os

# provision() exige MISTRAL_API_KEY dans l'environnement (secret partagé entre instances,
# cf. ops/provision_client.py::_shared_secret) — sans cette valeur, l'échec se produirait
# avant même la création du service backend, ce qui fausserait les scénarios de rollback
# ci-dessous (pensés pour échouer plus tard, à la création du frontend). Même pattern que
# backend/tests/conftest.py : une valeur de test, jamais une vraie clé.
os.environ.setdefault("MISTRAL_API_KEY", "test-mistral-key-for-ci-only")
