# Outillage flotte (vendeur uniquement)

Scripts CLI pour provisionner, mettre à jour en masse et décommissionner les instances
SmartTicket dédiées à chaque client — le "vrai" outil de gestion de la flotte tant que le
nombre de clients reste petit (1-5), avant qu'une vraie interface graphique (Phase 3 de
`docs/FLEET_PROVISIONING_PLAN.md`) ne soit justifiée.

**Ce dossier n'est jamais déployé sur une instance client** : ni `backend/Dockerfile` ni
`frontend/Dockerfile` ne le copient (leurs contextes Docker sont respectivement `./backend`
et `./frontend`, pas la racine du repo).

## ⚠️ Statut : non validé contre un vrai compte Render

Ces scripts sont écrits à partir de la documentation publique de l'API Render, mais
**jamais exécutés contre un vrai compte** (cf. Phase 0, encore non cochée, de
`docs/FLEET_PROVISIONING_PLAN.md`). Avant tout client réel :

1. Lancer chaque script avec `--dry-run` d'abord.
2. Provisionner une instance de **test jetable** (pas un client réel) et vérifier de bout
   en bout : base créée et migrée, services accessibles, domaine et certificat TLS si
   utilisés, entrée correcte dans `instances.db`.
3. Tester un vrai cycle backup/restore sur cette instance de test.
4. Seulement ensuite, provisionner un premier client réel.

Si un endpoint de l'API Render ne se comporte pas comme attendu, le point de correction
unique est `render_client.py` (tous les appels HTTP y passent par la fonction `_request`).

## Prérequis

```bash
pip install -r requirements.txt
export RENDER_API_KEY=...       # Render → Account Settings → API Keys
export MISTRAL_API_KEY=...      # secret partagé entre toutes les instances (pour l'instant)
export BREVO_API_KEY=...        # optionnel — sans lui, les emails sont juste loggés côté client
export SMTP_FROM=...            # OBLIGATOIRE si BREVO_API_KEY est définie, cf. ci-dessous
```

**`SMTP_FROM` doit être une adresse validée dans Brevo → Senders** (Brevo répond 401 sur
*tout* envoi sinon — bug réel rencontré le 2026-07-16 : la clé API était valide, seule
l'adresse expéditrice ne l'était pas). Cette variable sert deux usages distincts :

- L'email de bienvenue envoyé par `notify.py` à la fin du provisioning (lien de setup).
- Sans elle, `provision()` **refuse de démarrer** dès que `BREVO_API_KEY` est définie (échec
  rapide, avant tout appel Render) : injectée dans l'environnement de CHAQUE instance
  provisionnée pour que `backend/email_utils.py` (emails de vérification/reset) l'utilise
  aussi — sans quoi le backend serait retombé sur son adresse par défaut
  (`no-reply@smartticket.app`), jamais validée nulle part, et ses emails auraient échoué en
  401 silencieusement (l'erreur est interceptée et seulement loggée côté backend).

En test : une adresse Gmail validée manuellement suffit. En production : une adresse sur le
domaine (ex: `noreply@smartticket.fr`) avec SPF/DKIM configurés côté Brevo.

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Couvre aujourd'hui le rollback best-effort de `provision()` sur échec partiel
(`tests/test_provision_rollback.py`) — succès complet, rollback complet, rollback incomplet,
et le blocage d'un retry sur un slug "brûlé" — via `render_client`/`notify` entièrement
mockés (jamais d'appel réseau réel). Aucun autre script du dossier n'a de test dédié pour
l'instant.

`instances.db` (SQLite) est créé automatiquement au premier appel, dans ce dossier. Il
n'est jamais versionné (`*.db` déjà ignoré par le `.gitignore` racine) — c'est une base
locale au poste du vendeur, pas une ressource partagée. **Penser à la sauvegarder** (copier
le fichier) : elle contient les `VENDOR_KEY`/`ADMIN_SETUP_KEY` de toutes les instances.

## Scripts

### `provision_client.py` — créer une instance

```bash
python provision_client.py --name "Acme Corp" --slug acme-corp --admin-email admin@acme.com --postgres-plan starter --dry-run
python provision_client.py --name "Acme Corp" --slug acme-corp --admin-email admin@acme.com --postgres-plan starter
```

- `--postgres-plan` ne peut jamais être `free` (aucun backup automatique sur ce plan,
  décision actée dans le plan — refusé explicitement par le script).
- `--admin-email` : email du compte admin du client, utilisé pour `ADMIN_EMAIL` sur
  l'instance et comme destinataire du lien de setup.
- `--domain` (optionnel) attache un sous-domaine personnalisé (`{slug}.{domain}`) — suppose
  un domaine déjà possédé avec un enregistrement DNS wildcard pointant vers Render (Phase 0
  du plan, pas automatisé ici). Sans `--domain`, l'instance reste sur ses URLs
  `*.onrender.com`.
- Idempotent par rejet : refuse de continuer si le `--slug` existe déjà dans `instances.db`
  plutôt que de dupliquer les ressources.
- La logique métier vit dans `provision(...)`, une fonction pure (sans `input()`/`print()`
  comme moyen de retour) appelable directement — `main()` n'est qu'un mince wrapper CLI.
- **Aucun mot de passe en clair** : le compte admin est créé avec un mot de passe aléatoire
  jamais communiqué, en attente d'un `ADMIN_SETUP_TOKEN` à usage unique et expirant (défaut
  48h). Le script affiche une fois, en fin d'exécution, `VENDOR_KEY` (coupe-circuit
  d'abonnement, à conserver) et le lien `.../setup?token=...`.
- **Email de bienvenue automatique** (`notify.py`, API Brevo) : envoyé au client une fois
  l'instance active, avec le lien de setup. Si `BREVO_API_KEY` est absente ou que l'appel
  échoue, un WARNING/ERROR visible s'affiche et le lien reste de toute façon imprimé en
  console par `provision_client.py` — à transmettre manuellement dans ce cas. `notify.py`
  est volontairement indépendant de `backend/email_utils.py` (pas de dépendance `ops/` →
  `backend/`), au prix d'une petite duplication de l'appel HTTP à Brevo.

### `update_all_instances.py` — propager un correctif à toute la flotte

```bash
python update_all_instances.py --dry-run
python update_all_instances.py --only acme-corp,contoso   # rollout progressif
python update_all_instances.py                             # toutes les instances actives
```

Déclenche un redeploy Render (backend + frontend) pour chaque instance — suffisant grâce à
la décision mono-repo/mono-branche : toutes les instances suivent la même branche `main`,
donc pas de merge par client, juste un redémarrage sur le code déjà poussé.

### `delete_client.py` — décommissionner un client

```bash
python delete_client.py --slug acme-corp --dry-run
python delete_client.py --slug acme-corp                  # confirmation interactive (retaper le slug)
python delete_client.py --slug acme-corp --yes             # sans confirmation (usage scripté)
python delete_client.py --slug acme-corp --keep-row        # garde une trace dans instances.db (statut 'supprimee')
```

Action **irréversible** côté Render (suppression définitive de la base du client, y compris
ses backups). Confirmation explicite requise sauf `--yes`.

## Consulter la flotte (CLI + SQL, pas d'interface)

```bash
sqlite3 ops/instances.db "SELECT slug, client_name, statut, frontend_url, date_creation FROM instances"
```

## Ce qui n'est volontairement pas fait ici

- **Panel graphique** (Phase 3 du plan) — explicitement hors scope tant que la gestion en
  CLI + SQL reste confortable (1-5 clients). À reconsidérer seulement si cette limite
  commence réellement à peser.
- **Métering d'usage Mistral par client** (`usage_mensuel`, Phase 1 du plan) — nécessaire
  avant de pouvoir facturer/plafonner un client à fort usage, pas encore implémenté.

## Rollback sur échec partiel du provisioning

Si une étape de `provision()` échoue en cours de route (après la création d'au moins une
ressource Render), un rollback best-effort se déclenche automatiquement : les ressources déjà
créées sont supprimées **en ordre inverse de création**, en continuant même si l'une des
suppressions échoue (`render_client.delete_resources()`, la même logique que
`delete_client.py`).

- **Rollback complet** (tout a pu être supprimé) : la ligne est retirée de `instances.db`, le
  slug redevient utilisable pour un nouvel essai.
- **Rollback incomplet** (au moins une ressource n'a pas pu être supprimée) : la ligne reste
  dans `instances.db` avec `statut='failed'` et les IDs Render orphelins dans `notes` — le
  slug est alors **bloqué** (`slug_exists()` le refuse) tant qu'un humain n'a pas nettoyé
  manuellement ces ressources sur le dashboard Render et supprimé la ligne à la main. Ne
  jamais relancer un provisioning sur un slug dans cet état sans ce nettoyage préalable —
  retenter créerait de nouvelles ressources dont le nom (`smartticket-{slug}-*`) peut déjà
  être pris par les orphelines encore existantes.

Dans les deux cas, le message d'erreur retourné (`ProvisionResult.error`) liste explicitement
les ressources non supprimées — jamais masqué.
