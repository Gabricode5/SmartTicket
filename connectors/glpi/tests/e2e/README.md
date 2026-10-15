# Bout-en-bout contre une vraie instance GLPI

`test_glpi_docker.py` s'exécute uniquement si `GLPI_E2E_URL`, `GLPI_E2E_APP_TOKEN` et
`GLPI_E2E_USER_TOKEN` sont définis — sinon il est **skippé** (jamais un faux rouge).

Le bout-en-bout HTTP « de notre côté » (client → HTTP → suivi privé) est lui déjà couvert
sans Docker par `tests/test_e2e_http.py` (serveur GLPI stub local). Ce test-ci ajoute la
seule chose que le stub ne peut pas prouver : **que GLPI lui-même accepte notre payload**
(route `ITILFollowup`, noms de champs, en-têtes d'auth) et enregistre le suivi comme privé.

## Mise en route

```bash
# 1. Démarrer GLPI + MariaDB (mot de passe MariaDB jetable, local, à ta convenance)
export GLPI_E2E_DB_PASSWORD=<choisis-une-valeur>
docker compose -f tests/e2e/docker-compose.e2e.yml up -d

# 2. Installer GLPI : http://localhost:8088  → assistant d'installation
#    (BDD : hôte glpi-e2e-db, base/user = glpi, mot de passe = $GLPI_E2E_DB_PASSWORD).
#    Se connecter en glpi/glpi.

# 3. Activer l'API REST : Configuration → Générale → API
#    - « Activer l'API REST » = Oui
#    - noter l'« URL de l'API » (ex: http://localhost:8088/apirest.php)
#    - ajouter un client API → récupérer l'App-Token

# 4. Créer un jeton utilisateur : Préférences (compte) → « Jetons d'API »
#    → régénérer le « jeton d'API » → c'est le user_token

# 5. Lancer le test
export GLPI_E2E_URL=http://localhost:8088/apirest.php
export GLPI_E2E_APP_TOKEN=xxxxxxxx
export GLPI_E2E_USER_TOKEN=yyyyyyyy
# optionnel : réutiliser un ticket existant au lieu d'en créer un
# export GLPI_E2E_TICKET_ID=1
pytest tests/e2e -q
```

## Nettoyage

```bash
docker compose -f tests/e2e/docker-compose.e2e.yml down -v
```

`DRY_RUN=false` est le comportement testé ici (forcé dans le fichier de test). Le défaut
du projet reste `DRY_RUN=true`.
