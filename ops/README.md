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
```

**Isolation des secrets vendeur par instance (2026-08-19, ROADMAP.md bloquant sécurité/RGPD
n°3)** : `MISTRAL_API_KEY`/`BREVO_API_KEY` ne sont plus des variables d'environnement
partagées lues implicitement par `provision()` — chaque client a sa PROPRE clé, créée
manuellement dans la console Mistral (et Brevo si les emails transactionnels sont voulus)
AVANT le provisioning, et passée explicitement :

```bash
python provision_client.py --name "Acme Corp" --slug acme-corp --admin-email admin@acme.com \
    --postgres-plan starter --mistral-api-key "clé Mistral d'Acme Corp" \
    --brevo-api-key "clé Brevo d'Acme Corp"      # optionnel
```

Pourquoi : une clé partagée entre tous les clients ne peut être ni révoquée ni attribuée par
client, et une fuite compromet toute la flotte — un vrai no-go DPO pour la cible secteur
régulé. Vérifié (pas supposé) : ni Mistral ni Brevo n'exposent d'API de création
programmatique de sous-comptes/clés hors de leur tier Enterprise (sur devis) — la création
reste donc manuelle dans les deux consoles web, une clé par client, à chaque provisioning.

`--sender-domain` (défaut `smartticket.fr`, variable `SMTP_SENDER_DOMAIN` pour surcharger) :
l'adresse expéditrice des emails n'est **pas** demandée par client — elle est calculée
automatiquement (`noreply+{slug}@{domaine}`), pour n'avoir qu'un seul domaine à authentifier
(SPF/DKIM/DMARC) côté SmartTicket plutôt qu'un domaine vérifié par client (friction
d'onboarding jugée disproportionnée à cette échelle). **Ce domaine doit être RÉELLEMENT
authentifié dans Brevo → Senders avant tout client réel avec `--brevo-api-key` posée** —
sans quoi Brevo répond 401 sur *tout* envoi (bug réel rencontré le 2026-07-16, avant que
l'expéditeur soit calculé automatiquement plutôt que fourni à la main) ; aucune vérification
automatique de ce prérequis n'est faite par le script.

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
python provision_client.py --name "Acme Corp" --slug acme-corp --admin-email admin@acme.com --postgres-plan starter --mistral-api-key "clé Mistral d'Acme Corp" --dry-run
python provision_client.py --name "Acme Corp" --slug acme-corp --admin-email admin@acme.com --postgres-plan starter --mistral-api-key "clé Mistral d'Acme Corp"
```

- `--postgres-plan` ne peut jamais être `free` (aucun backup automatique sur ce plan,
  décision actée dans le plan — refusé explicitement par le script).
- `--admin-email` : email du compte admin du client, utilisé pour `ADMIN_EMAIL` sur
  l'instance et comme destinataire du lien de setup.
- `--domain` (optionnel) attache un sous-domaine personnalisé (`{slug}.{domain}`) — suppose
  un domaine déjà possédé avec un enregistrement DNS wildcard pointant vers Render (Phase 0
  du plan, pas automatisé ici). Sans `--domain`, l'instance reste sur ses URLs
  `*.onrender.com` — **jamais devinées** (bug réel du 2026-08-15 : Render peut assigner une
  URL différente du nom de service demandé, suffixe supplémentaire imprévisible), toujours
  relues depuis l'API après coup. Conséquence : le backend est redéployé une seconde fois une
  fois l'URL réelle du frontend connue (CORS_ORIGINS/FRONTEND_URL ne peuvent être correctes
  qu'à ce moment-là) — un provisioning sans `--domain` prend donc un peu plus longtemps
  qu'avant ce correctif.
- Idempotent par rejet : refuse de continuer si le `--slug` existe déjà dans `instances.db`
  plutôt que de dupliquer les ressources.
- La logique métier vit dans `provision(...)`, une fonction pure (sans `input()`/`print()`
  comme moyen de retour) appelable directement — `main()` n'est qu'un mince wrapper CLI.
- **Aucun mot de passe en clair** : le compte admin est créé avec un mot de passe aléatoire
  jamais communiqué, en attente d'un `ADMIN_SETUP_TOKEN` à usage unique et expirant (défaut
  48h). Le script affiche une fois, en fin d'exécution, `VENDOR_KEY` (coupe-circuit
  d'abonnement, à conserver) et le lien `.../setup?token=...`.
- **Email de bienvenue automatique** (`notify.py`, API Brevo) : envoyé au client une fois
  l'instance active, avec le lien de setup, via la même clé/expéditeur dédiés que le reste
  de l'instance (`--brevo-api-key` + adresse calculée, cf. ci-dessus — avant le 2026-08-19,
  `notify.py` lisait ses propres variables partagées, donc cet email restait mutualisé même
  après avoir isolé le reste). Si `--brevo-api-key` est absente ou que l'appel échoue, un
  WARNING/ERROR visible s'affiche et le lien reste de toute façon imprimé en console par
  `provision_client.py` — à transmettre manuellement dans ce cas. `notify.py` est
  volontairement indépendant de `backend/email_utils.py` (pas de dépendance `ops/` →
  `backend/`), au prix d'une petite duplication de l'appel HTTP à Brevo.
- **Séparation site vitrine / instance client** (2026-08-15) : le frontend affichait la
  landing marketing SmartTicket ("Essayer gratuitement", "Propulsé par Mistral AI"...) à sa
  racine `/`, y compris sur les instances clientes — inacceptable pour le public d'un client
  (secteur régulé). `provision()` pose `NEXT_PUBLIC_BRAND_NAME` (nom du client, déjà en
  place) **et** `NEXT_PUBLIC_DEPLOYMENT_MODE=instance` dans l'environnement du frontend,
  AVANT son premier build (même piège de timing que `NEXT_PUBLIC_API_URL` : bakée au build,
  jamais réévaluée au runtime). En mode `instance` (le défaut si la variable est absente —
  choix délibérément sécurisé, cf. `frontend/lib/deploymentMode.ts`), `frontend/proxy.ts`
  redirige `/` vers `/chat` (accès invité direct à l'assistant IA) au lieu de servir la
  landing. Le déploiement de démo (`smartticket-frontend` sur Render, futur `smartticket.fr`)
  n'est **pas** créé par `provision()` — il faut lui poser manuellement
  `NEXT_PUBLIC_DEPLOYMENT_MODE=marketing` sur Render pour qu'il continue de servir la landing.

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
ses backups). Confirmation explicite requise sauf `--yes`. `RENDER_API_KEY` est validée dès
le départ (avant la confirmation, avant toute suppression) — une clé manquante ne doit jamais
permettre d'atteindre la modification d'`instances.db` (bug réel du 2026-07-16, cf. section
suivante).

Si au moins une des 3 suppressions Render échoue, la ligne **n'est jamais retirée** —
symétrique du rollback de `provision()` ci-dessous : elle reste dans `instances.db` avec
`statut='deletion_failed'` et les IDs des ressources orphelines dans `notes`, pour qu'elles
restent traçables. `--keep-row` n'a d'effet que sur le cas de succès complet (statut
`'supprimee'` au lieu du retrait pur et simple) ; en cas d'échec la ligne reste de toute façon.

### `audit_render_resources.py` — auditer les ressources Render (lecture seule)

```bash
python audit_render_resources.py                              # préfixe par défaut : smartticket-test-
python audit_render_resources.py --prefix smartticket-acme-
```

N'appelle que `GET /services` et `GET /postgres` — **aucune mutation possible**. Liste
toutes les ressources dont le nom commence par le préfixe donné (nom, id, type, statut, date
de création, URL dashboard) et signale celles qui n'ont **aucune ligne correspondante** dans
`instances.db` : utile après un changement de poste (le registre local est gitignoré, cf.
Prérequis) ou pour retrouver d'éventuelles ressources orphelines laissées par un
`delete_client.py` antérieur au correctif du 2026-07-16.

### `fleet_admin.py` — page de gestion de flotte (LOCALE UNIQUEMENT)

```bash
cd ops && python fleet_admin.py
# -> http://127.0.0.1:8765
```

⚠️ **Ne tourne QUE sur ce poste, ne jamais l'exposer au-delà de 127.0.0.1** (pas de
`--host 0.0.0.0`, pas de reverse proxy public) : cette page peut suspendre, réactiver ou
(bientôt) créer des ressources Render **payantes**, et agit directement sur le compte
d'abonnement de vraies instances clientes. Elle n'est jamais déployée (comme le reste de
`ops/`) et ne réimplémente rien : elle lit `instances.db`, appelle l'API Render en lecture
(mêmes fonctions que `audit_render_resources.py`) et `provision()`/`delete_client()`
directement — le coupe-circuit d'abonnement (`GET`/`PUT /v1/instance/subscription-status`,
`backend/routers/instance.py`) n'est pas réimplémenté non plus, juste appelé.

État actuel :

- **Partie B.1 (lecture)** : liste des instances croisée avec l'API Render (statut,
  ressources manquantes, ressources orphelines), santé (ping direct du `GET /` de chaque
  instance — un service Render peut être "live" alors que l'appli plante au runtime), liens
  dashboard. Dégrade proprement sans `RENDER_API_KEY` (reste utilisable en local-only).
- **Partie B.2 (suspendre/réactiver)** : statut d'abonnement réel par instance (distinct du
  statut Render — une instance peut être "live" côté Render mais "suspended" côté abonnement,
  402 pour ses utilisateurs finaux), boutons suspendre/réactiver avec confirmation
  **obligatoire par saisie du slug** (impact direct sur les utilisateurs du client). Le
  résultat affiché après une action est toujours un **re-GET réel**, jamais un succès supposé.
  `vendor_key` (le secret du coupe-circuit) n'est stocké que côté serveur Python et n'apparaît
  JAMAIS dans le HTML rendu ni dans une URL — vérifié par test
  (`test_vendor_key_never_appears_in_rendered_html`). Une instance dont le `vendor_key` est
  absent en base (ex: provisionnée avant son ajout au schéma) affiche un message explicite et
  désactive l'action plutôt que de planter.
- **Partie B.2bis (supprimer + cycle de vie)** : bouton "Supprimer définitivement" par
  instance, qui appelle `delete_client.delete_instance()` — la MÊME fonction que la CLI (le
  script `delete_client.py` a été refactoré pour l'exposer, exactement comme `provision()`
  dans `provision_client.py` : logique pure d'un côté, CLI mince de l'autre). Irréversible,
  donc garde-fous **plus stricts** que la suspension : confirmation par saisie du slug **PLUS**
  une case à cocher explicite ("je comprends que les données seront détruites"). Une instance
  suspendue depuis longtemps affiche un rappel de facturation (cf. ci-dessous). Disponible
  pour toute instance dont le statut local n'est pas déjà `'supprimee'`.
- **Partie B.3 (créer une instance)** : formulaire (nom, email admin, plan Postgres, clé API
  Mistral dédiée au client — requise —, clé API Brevo dédiée — optionnelle, cf. isolation des
  secrets vendeur ci-dessus) qui appelle `provision_client.provision()` — la MÊME fonction
  que la CLI, rien réimplémenté.
  `provision()` prend ~5 minutes en conditions réelles (confirmé) : lancée dans un **thread
  daemon séparé**, la requête HTTP répond immédiatement, jamais d'attente synchrone. Le slug
  est dérivé automatiquement du nom côté navigateur (minuscules, accents retirés, tirets —
  JS vanilla, aucune dépendance) mais reste un champ texte modifiable ; validé aussi
  côté serveur (format ET unicité) avant de lancer quoi que ce soit.

  **Suivi de la progression** : tant qu'un provisioning tourne, la page se recharge seule
  toutes les 10s (`<meta http-equiv="refresh">`, pas de JS de polling dédié) et affiche un
  état "en cours depuis X min". Le résultat final est toujours honnête — succès (lien de
  setup affiché, confirmation d'envoi de l'email de bienvenue) ou échec (message d'erreur
  réel ; le rollback est déjà géré par `provision()` elle-même, cf. rollback plus bas) —
  jamais un succès annoncé à tort.

  **Le suivi vit UNIQUEMENT en mémoire** (dict Python protégé par un verrou, pas de file de
  jobs persistante — le plus simple possible pour un outil local mono-utilisateur). Deux
  conséquences assumées, documentées, pas des bugs : si le serveur est arrêté (Ctrl+C)
  pendant un provisioning en cours, (1) le suivi visuel du job est perdu, mais `provision()`
  a déjà écrit la ligne `'provisioning'` dans `instances.db` dès le début et la met à jour au
  fil de l'eau — l'instance reste donc visible dans le tableau principal et son état réel
  retrouvable via cette même page ou `audit_render_resources.py`, exactement comme pour la
  coupure réseau déjà rencontrée en conditions réelles (aucune reprise automatique, à
  nettoyer manuellement le cas échéant) ; (2) l'historique des jobs terminés disparaît aussi
  au redémarrage — `instances.db` reste la seule source de vérité durable.

  Le lien de setup (token à usage unique, expirant) s'affiche en clair sur la page une fois
  le provisioning terminé — acceptable pour un outil local mono-utilisateur, mais à garder en
  tête. `vendor_key`, lui, n'apparaît JAMAIS (même règle que pour suspendre/réactiver).

### ⚠️ Suspendre n'arrête PAS la facturation Render

**Point à retenir absolument** : `PUT /v1/instance/subscription-status` à `"suspended"`
coupe l'accès des utilisateurs finaux du client (402 sur `/v1/*`), mais **le conteneur
Render reste vivant** — le service continue d'être facturé normalement. Seul le
**déprovisionnement** (`delete_client.py` / bouton Supprimer) arrête réellement les coûts.

La page affiche un rappel ("suspendue depuis X jours — facturation Render toujours active")
calculé à partir du champ `updated_at` déjà renvoyé par
`GET /v1/instance/subscription-status` (colonne `updated_at` de
`models.InstanceSubscription`, auto-maintenue côté backend, `onupdate=func.now()`) — pas
besoin d'une colonne locale supplémentaire pour ça.

**Cycle recommandé** (décision manuelle à chaque étape, **pas d'automatisation** pour
l'instant — à l'échelle actuelle, 0 à quelques clients, supprimer un client automatiquement
serait trop risqué) :

1. Impayé constaté → **suspendre** depuis la page (coupe l'accès immédiatement).
2. Délai de grâce (ex. 15-30 jours, à la main du vendeur selon le contexte du client).
3. Si l'impayé persiste après ce délai → **supprimer** (déprovisionnement complet, arrête la
   facturation).

## Consulter la flotte (CLI + SQL, pas d'interface)

```bash
sqlite3 ops/instances.db "SELECT slug, client_name, statut, frontend_url, date_creation FROM instances"
```

## Ce qui n'est volontairement pas fait ici

- **Panel graphique hébergé, multi-utilisateur** (Phase 3 du plan) — distinct de
  `fleet_admin.py` ci-dessus (local, mono-utilisateur, jamais exposé) : reste hors scope
  tant que la gestion à ce niveau reste confortable (1-5 clients). À reconsidérer seulement
  si cette limite commence réellement à peser.
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
