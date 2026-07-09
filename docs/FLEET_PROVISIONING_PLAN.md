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
  - Partagés au démarrage (à revoir dès qu'un métering fiable existe, cf. Phase 1) : `MISTRAL_API_KEY`, `BREVO_API_KEY`
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

- [ ] Nouvelle base Postgres dédiée au panel (indépendante de toute base client) avec une
  table `instances` : `id`, `client_name`, `slug`, `render_backend_service_id`,
  `render_frontend_service_id`, `render_database_id`, `subdomain`, `plan_tarifaire`,
  `date_creation`, `date_facturation`, `statut` (`provisioning` / `active` / `suspendue`)
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
  connaître les contraintes réelles
- [ ] Prérequis DNS : posséder un nom de domaine dédié et configurer un enregistrement
  wildcard (`*.smartticket.fr` ou équivalent) pointant vers Render
- [ ] Écrire `provision_client.py --name "Client X" --slug client-x` qui, dans l'ordre :
  1. Crée la base Postgres managée (équivalent du bloc `databases:` de `render.yaml`)
  2. Crée le service backend Docker avec les env vars générées (`SECRET_KEY` aléatoire,
     `DATABASE_URL` de la DB créée à l'étape 1, `ADMIN_SETUP_KEY` aléatoire propre à
     l'instance, `BREVO_API_KEY`/`MISTRAL_API_KEY` partagés, `CORS_ORIGINS` pointant
     directement vers le sous-domaine final `{slug}.smartticket.fr`)
  3. Crée le service frontend Docker avec `NEXT_PUBLIC_API_URL` pointant vers le backend
     créé à l'étape 2
  4. Attache le custom domain `{slug}.smartticket.fr` au service frontend via l'API Render
  5. Attend que les deux déploiements soient "live" **et** que le certificat TLS du custom
     domain soit émis (comportement auto de Render, à confirmer sur un premier essai réel
     plutôt qu'à supposer) avant de considérer l'instance prête
  6. Enregistre l'instance dans la table `instances` du panel interne (Phase 1)
  7. Génère le lien d'amorçage admin (cf. ci-dessous) et l'affiche/l'envoie au vendeur —
     jamais de mot de passe en clair dans les logs du script
- [ ] **Amorçage du compte admin sans mot de passe en clair** : le backend expose déjà
  `POST /v1/setup-admin`, protégé par le header `X-Setup-Key` (= `ADMIN_SETUP_KEY`, unique
  par instance, généré à l'étape 2) — pas besoin d'inventer un nouveau système de token.
  Il manque seulement une page frontend `/setup?key=...` (nouvelle, à créer, même famille
  que `/verify-email`/`/reset-password`) qui laisse le client choisir lui-même son
  username/email/mot de passe admin et appelle `/v1/setup-admin` avec la clé. Le script de
  provisioning envoie au client un lien `https://{slug}.smartticket.fr/setup?key=xxx` —
  zéro mot de passe généré côté vendeur qui transite par email
- [ ] Gérer l'idempotence : que fait le script si on le relance avec un `slug` déjà utilisé ?
  (refuser proprement plutôt que dupliquer les ressources)
- [ ] Documenter la procédure de **suppression** d'une instance (offboarding client) —
  symétrique du provisioning, à ne pas négliger

## Phase 2 bis — Mise à jour de masse de la flotte

Le vrai problème opérationnel n'est pas la création d'une instance (faite une fois par
client) mais la propagation d'un correctif ou d'une nouvelle fonctionnalité aux N
instances existantes. Sans ça, dès le 5e client, chaque fix de bug devient un redéploiement
manuel répété N fois sur le dashboard Render.

- [ ] `update_all_instances.py` qui boucle sur la table `instances` (statut `active`) et
  déclenche un redeploy via l'API Render (`POST /deploys` sur chaque
  `render_backend_service_id`/`render_frontend_service_id`) — cohérent avec la décision
  mono-branche : toutes les instances déploient la même branche `main`, donc un redeploy
  suffit, pas de merge/rebase par client
- [ ] Mode `--dry-run` (liste ce qui serait redéployé sans le faire) et mode
  `--only slug1,slug2` (rollout progressif : tester sur 1-2 clients avant tout le monde)

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
