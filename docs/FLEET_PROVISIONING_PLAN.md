# Plan — Infrastructure de vente (flotte d'instances)

Découpage des chantiers de la section "Stratégie de commercialisation" du `ROADMAP.md`
(provisioning scripté, mise à jour de la flotte, panel interne) en étapes concrètes, dans
l'ordre où elles doivent être attaquées. Ce document sert de plan de travail — les cases
se cochent au fur et à mesure, comme dans `ROADMAP.md`.

Rappel du contexte : flotte d'instances séparées (1 Postgres + 1 backend + 1 frontend par
client, isolation physique des données), pas de vrai multi-tenant. Objectif final : un
script capable de créer une instance client complète et accessible sous son propre
sous-domaine en une seule commande, et un second script capable de propager un correctif
à toute la flotte.

**Décision de fond, à ne jamais remettre en cause tant que le projet est piloté seul** :
mono-repo, mono-branche pour tous les clients. Un déploiement homogène (même code partout)
est la seule option gérable en solo — des branches par client pour permettre de la
personnalisation créeraient une divergence de code impossible à maintenir dès le 3e ou 4e
client.

---

## Phase 0 — Décisions à figer avant d'écrire la moindre ligne de code

- [ ] Vérifier que le plan Render actuel permet l'usage de l'**API Render** (création
  programmatique de services/DB) — certaines opérations de provisioning peuvent nécessiter
  un plan payant au-delà du plan gratuit utilisé aujourd'hui pour l'instance de démo
- [ ] Générer un **token API Render** (Account Settings → API Keys) et vérifier ses
  permissions (création de services, de bases de données, gestion des domaines)
- [ ] Convention de nommage des ressources par client (ex: services `smartticket-{slug}-backend`
  / `smartticket-{slug}-frontend`, DB `smartticket-{slug}-postgres`, où `slug` est un
  identifiant court dérivé du nom du client, ex: `acme-corp`)
- [ ] Décider quels secrets sont **partagés** entre tous les clients vs **uniques par
  instance** :
  - Uniques par instance (obligatoire) : `SECRET_KEY`, `DATABASE_URL`, `ADMIN_SETUP_KEY` (cf. Phase 2)
  - Partagés au démarrage (à revoir dès qu'un métering fiable existe, cf. Phase 1) : `MISTRAL_API_KEY`, `BREVO_API_KEY`, `SMTP_FROM`
    (cette dernière **obligatoire** dès que `BREVO_API_KEY` est définie — doit être une adresse
    validée dans Brevo → Senders, sinon 401 silencieux sur tous les emails, bug réel du
    2026-07-16, cf. `ops/README.md`)
- [x] Vérifier la **politique de backup** du plan Render retenu — **tranché (2026-07-09)** :
  le plan Free (celui de l'instance de démo actuelle) n'offre **aucun backup automatique**
  (onglet "Recovery" présent dans le dashboard mais sans point-in-time recovery ni snapshots
  réguliers sur ce plan) et les bases Postgres gratuites sont soumises à une politique
  d'expiration Render. **Conséquence directe : chaque instance client doit être provisionnée
  sur un plan Postgres payant** (Starter ou supérieur, backups quotidiens avec rétention
  configurable) — jamais sur Free. Cohérent avec l'estimation ~40-60€/mois déjà posée dans
  ce document, qui supposait implicitement un plan payant. À intégrer dans `provision_client.py`
  (Phase 2) : choix explicite du plan Postgres, pas de valeur par défaut Free
- [ ] Décider où vit le **panel interne** : un nouveau petit projet séparé du repo
  SmartTicket (recommandé — c'est un outil vendeur, pas une fonctionnalité vendue aux
  clients ; un bug dedans ne doit jamais pouvoir toucher un déploiement client), ou un
  dossier isolé dans ce repo. **Recommandation : projet séparé.**

## Phase 1 — Modèle de données du panel interne

- [x] **Écart assumé par rapport au plan initial** : table `instances` créée dans **SQLite**
  (`ops/instances.db`, schéma dans `ops/db.py`), pas dans un Postgres dédié comme envisagé
  ici. À l'échelle visée (1-5 clients, gestion en CLI + une requête SQL, zéro interface
  graphique — cf. "Étape A" ci-dessous), payer et administrer un Postgres managé rien que
  pour une poignée de lignes est disproportionné. Un fichier local, jamais versionné,
  sauvegardable en copiant un fichier. Migration vers Postgres réenvisageable plus tard si
  le volume ou un besoin d'accès concurrent le justifie. Colonnes : `id`, `client_name`,
  `slug`, `render_backend_service_id`, `render_frontend_service_id`, `render_database_id`,
  `backend_url`, `frontend_url`, `subdomain`, `vendor_key`, `admin_setup_key`,
  `plan_tarifaire`, `statut` (`provisioning`/`active`/`suspendue`/`supprimee`),
  `date_creation`, `date_facturation`, `notes`
- [ ] Table `usage_mensuel` (`instance_id`, `tokens_consommes`, `mois`) — **nécessaire dès
  que `MISTRAL_API_KEY` est partagée entre clients**, sinon impossible de savoir quel
  client consomme le budget avant la facture Mistral de fin de mois. Implique d'abord que
  chaque instance client logue le nombre de tokens par appel — **absent aujourd'hui de
  `ai_call_logs`** (seuls latence, nombre de chunks RAG et succès/échec sont trackés, pas
  les tokens) : ajouter cette colonne côté produit avant de pouvoir agréger quoi que ce
  soit côté panel. Le panel interroge ensuite périodiquement chaque instance via un
  endpoint agrégateur dédié et protégé (ex: `GET /v1/analytics/usage-mensuel`)

## Phase 2 — Script de provisioning automatisé (inclut le sous-domaine)

Le sous-domaine doit être attaché **dans la même exécution** que la création des services,
pas dans une phase séparée ultérieure : `CORS_ORIGINS` du backend et `NEXT_PUBLIC_API_URL`
du frontend référencent le sous-domaine final dès leur création, et un état intermédiaire
"instance provisionnée mais accessible seulement via l'URL `*.onrender.com`" ne sert à
rien et complique le debug (un test de CORS avant l'attachement du domaine donnerait un
faux résultat).

- [ ] Explorer concrètement l'API Render (endpoints réels : création de service Postgres
  managé, création de service web Docker lié à un repo GitHub + branche + `dockerfilePath`,
  ajout de variables d'environnement, ajout d'un custom domain) — à valider avec un appel
  de test avant d'écrire le script complet, la doc publique ne suffit pas toujours à
  connaître les contraintes réelles. **`ops/render_client.py` écrit à partir de la doc
  publique mais encore non exécuté contre un vrai compte** — cette case reste à cocher
  seulement après un premier appel réel réussi (cf. avertissement en tête de `ops/README.md`)
- [ ] Prérequis DNS : posséder un nom de domaine dédié et configurer un enregistrement
  wildcard (`*.smartticket.fr` ou équivalent) pointant vers Render — pas encore fait, décision
  vendeur hors scope du code
- [x] Écrire `provision_client.py --name "Client X" --slug client-x` — `ops/provision_client.py`,
  suit les 7 étapes ci-dessous. **Code écrit et testé en `--dry-run`/erreurs (plan `free`
  refusé, idempotence) uniquement — jamais exécuté contre un vrai compte Render (Phase 4 du
  plan reste à faire avant tout client réel)** :
  1. Crée la base Postgres managée (équivalent du bloc `databases:` de `render.yaml`)
  2. Crée le service backend Docker avec les env vars générées (`SECRET_KEY` aléatoire,
     `DATABASE_URL` de la DB créée à l'étape 1, `ADMIN_SETUP_TOKEN` aléatoire propre à
     l'instance (à usage unique, expirant), `BREVO_API_KEY`/`MISTRAL_API_KEY`/`SMTP_FROM` partagés,
     `CORS_ORIGINS` pointant directement vers le sous-domaine final `{slug}.smartticket.fr`)
  3. Crée le service frontend Docker avec `NEXT_PUBLIC_API_URL` pointant vers le backend
     créé à l'étape 2
  4. Attache le custom domain `{slug}.smartticket.fr` au service frontend via l'API Render
     (si `--domain` fourni ; sans lui, reste sur les URLs `*.onrender.com`)
  5. Attend que les deux déploiements soient "live" (`render_client.wait_for_deploy_live`,
     polling avec timeout) — attente du certificat TLS du custom domain **non implémentée
     séparément**, à vérifier lors du premier essai réel si Render ne le fait pas de façon
     transparente
  6. Enregistre l'instance dans la table `instances` (SQLite, cf. Phase 1)
  7. Affiche `VENDOR_KEY` et le lien `/setup?token=...` une seule fois en console (pas écrit
     sur disque, pas loggé) — cf. point suivant, aucun mot de passe ne transite jamais en
     clair côté opérateur
- [x] **Amorçage du compte admin sans mot de passe en clair** — **implémenté différemment de
  ce qui était envisagé ci-dessus** : plutôt que de réutiliser `POST /v1/setup-admin` (header
  `X-Setup-Key` statique, non expirant, réutilisable indéfiniment — pas le bon outil pour un
  flux client), un mécanisme dédié a été construit : `ADMIN_SETUP_TOKEN` (aléatoire, à usage
  unique, expirant — `ADMIN_SETUP_TOKEN_EXPIRE_HOURS`, défaut 48h) généré par
  `provision_client.py` et consommé par une nouvelle route `POST /v1/setup` (`backend/routers/
  auth.py`) plus une page frontend `/setup?token=...` (même famille que `/verify-email`/
  `/reset-password`) qui laisse le client choisir username/email/mot de passe. `/setup-admin`
  reste dans le code mais est **redescendu au rang d'outil de secours dev/test uniquement**
  (cf. `backend/tests/conftest.py`, qui s'appuie dessus comme raccourci de bootstrap dans une
  dizaine de fichiers de tests) : `provision_client.py` ne pose plus `ADMIN_SETUP_KEY` sur les
  instances client, ce qui rend la route inerte (403 systématique) sur toute instance de
  production, en plus d'un rate limit désormais posé dessus par cohérence avec `/setup`.
- [x] Gérer l'idempotence : que fait le script si on le relance avec un `slug` déjà utilisé ?
  `provision_client.py` refuse (vérifié réellement : relance sur un slug déjà présent dans
  `instances.db` → erreur explicite, code de sortie 1, aucun appel Render déclenché)
- [x] Documenter la procédure de **suppression** d'une instance (offboarding client) —
  `ops/delete_client.py` (symétrique du provisioning : supprime backend/frontend/Postgres
  côté Render, retire ou archive la ligne `instances.db`, confirmation interactive requise
  sauf `--yes`), documenté dans `ops/README.md`

## Phase 2 bis — Mise à jour de masse de la flotte

Le vrai problème opérationnel n'est pas la création d'une instance (faite une fois par
client) mais la propagation d'un correctif ou d'une nouvelle fonctionnalité aux N
instances existantes. Sans ça, dès le 5e client, chaque fix de bug devient un redéploiement
manuel répété N fois sur le dashboard Render.

- [x] `update_all_instances.py` qui boucle sur la table `instances` (statut `active`) et
  déclenche un redeploy via l'API Render (`POST /deploys` sur chaque
  `render_backend_service_id`/`render_frontend_service_id`) — cohérent avec la décision
  mono-branche : toutes les instances déploient la même branche `main`, donc un redeploy
  suffit, pas de merge/rebase par client. **Code écrit, jamais exécuté contre un vrai compte
  Render** (même statut que `provision_client.py` ci-dessus)
- [x] Mode `--dry-run` (liste ce qui serait redéployé sans le faire) et mode
  `--only slug1,slug2` (rollout progressif : tester sur 1-2 clients avant tout le monde) —
  les deux implémentés et vérifiés réellement (liste vide, filtrage par slugs, slugs
  inconnus signalés sans faire échouer le reste)

## Phase 3 — Panel interne (UI)

**Périmètre volontairement limité en V1 : lecture seule.** Une authentification par mot
de passe partagé est acceptable pour consulter des statuts, mais pas pour exposer des
actions destructrices (provisionner/supprimer une instance) — une fuite de ce mot de passe
donnerait alors accès à la suppression de toutes les instances clients. Les scripts
(`provision_client.py`, `update_all_instances.py`) restent exécutés en CLI par le vendeur
tant qu'une vraie authentification (pas un secret partagé) n'est pas en place. Des actions
dans le panel ne sont ajoutées que lorsque ce prérequis est satisfait.

- [ ] Interface minimale (réutiliser Next.js, stack déjà maîtrisée, ou un simple dashboard
  serveur si plus rapide à livrer) listant les instances : nom client, statut, lien vers
  les logs Render (lien externe direct, pas besoin de proxy l'API de logs), plan tarifaire,
  date de facturation, consommation du mois (table `usage_mensuel`, Phase 1)
- [ ] Statut santé par instance : ping périodique du `GET /` de chaque backend client (déjà
  utilisé comme `healthCheckPath` sur chaque instance, réutilisable tel quel)
- [ ] Authentification minimale en lecture seule (mot de passe partagé ou IP whitelist
  suffisent pour cette V1 — un seul utilisateur, pas besoin d'un système de rôles)

## Phase 4 — Validation end-to-end

- [ ] Provisionner une instance de test complète avec le script (pas un client réel),
  sous-domaine inclus dans le même run (Phase 2)
- [ ] Vérifier : DB créée et migrée automatiquement (le `run_migrations()` existant dans
  `main.py` s'en charge déjà au premier démarrage, aucune étape supplémentaire nécessaire
  ici), backend et frontend accessibles sous leur sous-domaine final, certificat TLS
  valide, entrée visible et correcte dans le panel interne, amorçage admin fonctionnel via
  `/setup?key=...`
- [ ] **Tester réellement un cycle backup/restore** sur cette instance de test : y injecter
  des données, déclencher/attendre un backup Render, restaurer, vérifier que les données
  sont bien là — avant le premier client payant, pas après. Un backup jamais restauré n'est
  pas un backup
- [ ] Tester `update_all_instances.py --dry-run` puis en conditions réelles sur cette
  instance de test
- [ ] Mesurer le temps total de bout en bout du provisioning (objectif : quelques minutes,
  pas des heures) et noter les points de friction restants
- [ ] Provisionner le ou les premiers **clients pilotes réels** avec ce même script

---

## Risques et points d'attention à garder en tête

- **Quota Render** : vérifier les limites du compte (nombre de services, nombre de bases)
  avant de promettre un onboarding rapide à un client
- **Coût par instance** (~40-60€/mois estimés) : le suivre réellement dès le premier client
  pilote pour confirmer les hypothèses de pricing du `ROADMAP.md`
- **Coût variable Mistral caché** : sans le métering de la Phase 1, un client à fort usage
  peut plomber la marge globale sans que ce soit visible avant la facture — cf. `usage_mensuel`
- **Secrets** : plus de mot de passe admin en clair à transmettre (cf. `/setup?key=...`,
  Phase 2) — le seul secret qui transite est `ADMIN_SETUP_KEY`, à usage unique et propre à
  l'instance, jamais loggé
- **Offboarding** : prévu symétriquement au provisioning (Phase 2), sinon des instances
  orphelines coûteront de l'argent sans générer de revenu
- **Backup jamais testé** : traité explicitement en Phase 4, avant tout client payant
- **Panel avec pouvoir destructeur** : explicitement exclu de la V1 (Phase 3) tant que
  l'authentification n'est pas plus robuste qu'un secret partagé
