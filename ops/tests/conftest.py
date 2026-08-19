"""provision() prend désormais mistral_api_key/brevo_api_key en paramètres explicites plutôt
que de les lire dans l'environnement (isolation des secrets vendeur par instance, 2026-08-19)
— plus rien à poser ici, cf. les tests eux-mêmes (_TEST_MISTRAL_KEY dans
test_provision_rollback.py)."""
