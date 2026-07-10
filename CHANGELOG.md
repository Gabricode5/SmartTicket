# Changelog

Toutes les évolutions notables de SmartTicket sont consignées ici.

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
Versioning : [Semantic Versioning](https://semver.org/lang/fr/)

## [Non publié]

### Ajouté
- Visite guidée au premier login, adaptée au rôle (`user`/`sav`/`superviseur`/`admin`) — modal léger sans dépendance externe (`frontend/components/onboarding/OnboardingModal.tsx`), rejouable depuis Paramètres → Aide
- Colonne `tenant_id` (UUID, valeur fixe unique par instance) sur les 6 tables principales, en préparation d'une future architecture multi-tenant — aucun changement de comportement, colonne non exposée via l'API

### Corrigé
- Envoi d'email : ajout d'un mode API HTTP Brevo (`BREVO_API_KEY`, prioritaire sur `SMTP_HOST`) en plus du SMTP générique — sur Render, le SMTP classique (port 587) était bloqué en sortie, puis rejeté par Brevo (`525 Unauthorized IP address`) faute d'IP de sortie fixe à whitelister. L'API HTTP passe par HTTPS classique et contourne ces deux limites
- `frontend/proxy.ts` (garde d'authentification) redirigeait `/verify-email` vers `/login` avant même que la page ne s'affiche — route absente de sa liste `isPublicPath`, alors qu'un visiteur n'y accède justement jamais authentifié. Le lien de vérification par email ne pouvait donc jamais fonctionner en production

### Sécurité
- `build_rag_prompt()` (prompt système envoyé au modèle IA) durci contre les tentatives de prompt-injection — pertinent depuis l'ouverture du chat anonyme public : la QUESTION de l'utilisateur est désormais explicitement étiquetée comme donnée, jamais une instruction système, avec refus explicite hors périmètre du support client

---

## [2.11.0] - 2026-07-10

### Ajouté
- Import en masse d'utilisateurs par CSV (admin) : `POST /v1/users/import-csv` accepte un fichier avec les colonnes `email`/`username`/`prenom`/`nom` (export type ERP d'entreprise), crée un compte `user` par ligne valide et envoie un email d'invitation ("créez votre mot de passe") à chacun via le mécanisme de réinitialisation de mot de passe existant. Lignes invalides, doublons (dans le fichier ou déjà en base) et erreurs individuelles sont rapportés sans bloquer le reste de l'import. Plafonné à `MAX_CSV_IMPORT_ROWS` (défaut 500) par import
- Nouveau bouton "Importer un CSV" dans l'espace admin (`frontend/components/dashboard/CsvImportDialog.tsx`)

---

## [2.9.0] - 2026-07-09

### Sécurité
- `POST /v1/register` n'avait aucun rate limiting, contrairement à `/login`/`/resend-verification`/`/forgot-password` — porte ouverte au spam de comptes jetables en inscription publique (contexte B2B2C). Ajout de `REGISTER_RATE_LIMIT` (défaut `5/hour`, configurable)

---

## [2.10.0] - 2026-07-09

### Ajouté
- Chat IA anonyme (B2B2C) : `POST /v1/sessions/guest` crée un compte "invité" silencieusement (aucune inscription requise) et démarre directement une conversation ; `POST /v1/me/claim` permet ensuite de transformer ce compte en compte réel (email + mot de passe) sans connaître de mot de passe existant. Nouvelle page publique `/chat` (démarre une session invité et redirige vers le chat) et bandeau "Créer un compte" affiché aux visiteurs anonymes dans `/ai-assistant/[id]`
- Purge automatique des comptes invités jamais réclamés après `GUEST_ACCOUNT_TTL_DAYS` (défaut 7 jours), intégrée au scheduler RGPD existant
- `GET /v1/users` exclut désormais les comptes invités des listes d'administration

---

## [2.8.0] - 2026-07-09

### Sécurité
- `POST /v1/sessions/{id}/close` n'indexe plus automatiquement le transcript/résumé du ticket dans la base de connaissances partagée — **rupture de comportement** : ce contenu (potentiellement des données personnelles d'un client final) pouvait auparavant remonter dans les réponses IA données à n'importe quel autre utilisateur. Comportement désormais opt-in via `INDEX_CLOSED_TICKETS=true` (défaut `false`), pertinent uniquement en usage B2B interne où tous les utilisateurs sont des collègues de confiance — jamais en support public B2B2C

---

## [2.7.0] - 2026-07-09

### Ajouté
- Réinitialisation de mot de passe : `POST /v1/forgot-password` envoie un lien de réinitialisation par email (JWT dédié, 1h, réponse générique anti-énumération, limité à 3/heure) ; `POST /v1/reset-password` valide le lien et met à jour le mot de passe. Nouvelles pages frontend `/forgot-password` (formulaire réel, remplace le stub non fonctionnel) et `/reset-password`

---

## [2.6.0] - 2026-07-08

### Ajouté
- Notifications in-app : quand un agent SAV répond à un ticket, le client est notifié (+ email best-effort) ; quand un ticket est transféré, toute l'équipe SAV/superviseur/admin est notifiée. Nouveaux `GET /v1/notifications`, `GET /v1/notifications/unread-count`, `PATCH /v1/notifications/{id}/read`, `POST /v1/notifications/read-all`
- Nouvelle table `notifications`, nouveau module `backend/notifications.py`
- `NotificationBell` (`frontend/components/NotificationBell.tsx`) dans la sidebar : badge non-lues (polling 20s), liste déroulante, clic → session concernée

---

## [2.5.0] - 2026-07-08

### Ajouté
- Vérification de l'adresse email à l'inscription : `POST /v1/register` envoie désormais un lien de confirmation (JWT dédié, 48h), `GET /v1/verify-email` le valide, `POST /v1/resend-verification` permet de le renvoyer (limité à 3/heure, message générique anti-énumération). `POST /v1/login` refuse désormais un compte dont l'email n'est pas vérifié (`403`, code `email_not_verified`)
- Nouveau `backend/email_utils.py` : envoi SMTP générique (compatible tout fournisseur — Brevo, SendGrid, Gmail...), avec repli sur un simple log si `SMTP_HOST` n'est pas configuré (dev local, tests, aucun compte SMTP requis)
- Nouvelles pages frontend `/verify-email` (confirmation + renvoi si lien expiré) et écran "Vérifiez votre boîte mail" après inscription ; `/login` propose de renvoyer le lien si le compte n'est pas encore vérifié

### Modifié
- Changer son adresse email (`PUT /v1/me`) réinitialise `email_verified` et renvoie un nouveau lien de confirmation — on ne peut pas hériter de la confiance accordée à l'ancienne adresse
- Les comptes admin (bootstrap au démarrage et `POST /v1/setup-admin`) sont automatiquement marqués comme vérifiés, n'étant jamais créés via l'inscription publique
- Comptes déjà existants sur une base déjà déployée (ex: Render) automatiquement marqués comme vérifiés à la première migration suivant ce déploiement (grandfathering) — aucun utilisateur existant n'est verrouillé hors de son compte

---

## [2.4.0] - 2026-07-07

### Ajouté
- Reranking hybride du pipeline RAG (`backend/rag_reranking.py`) : sur-échantillonnage des candidats pgvector puis reclassement par similarité + recouvrement lexical + feedback utilisateur accumulé par chunk
- Quarantaine automatique des chunks de la base de connaissances au feedback négatif répété
- `chat_messages.source_kb_ids` : traçabilité des chunks utilisés pour générer chaque réponse IA (nécessaire au reranking par feedback)

---

## [2.3.0] - 2026-07-07

### Ajouté
- Nouveau rôle `superviseur` : hérite de tous les droits d'un agent SAV (sessions transférées, base de connaissances, analytics) et peut en plus promouvoir/rétrograder un compte entre `user` et `sav` — sans jamais pouvoir toucher aux comptes `admin` ni éditer/supprimer un profil utilisateur
- `frontend/components/dashboard/SupervisorDashboard.tsx` : gestion de l'équipe SAV (promotion/rétrogradation) + file d'attente de tickets intégrée (réutilise `SavDashboard`)

### Corrigé
- `PUT /v1/users/{id}/role` et `PUT /v1/users/{id}` rejetaient `superviseur` avec `400 Rôle invalide` (liste blanche oubliée lors de l'ajout du rôle, attrapé par la CI)
- `AdminDashboard.tsx` ne récupérait ni n'affichait les comptes `superviseur` (colonne manquante), les rendant invisibles après promotion

---

## [2.2.0] - 2026-07-07

### Ajouté
- `GET /v1/analytics/stats/pdf` et `GET /v1/analytics/ai-metrics/pdf` : export PDF des tableaux de bord Analytics et Monitoring IA (`backend/pdf_export.py`)
- Export CSV côté client des mêmes tableaux de bord (`frontend/lib/csv.ts`), sans aller-retour serveur

---

## [2.1.0] - 2026-07-07

### Ajouté
- `GET /v1/sessions/search` : recherche full-text (Postgres `to_tsvector`/`plainto_tsquery`, config `french`) dans le contenu des messages et les titres de conversation, avec extrait surligné (`ts_headline`). Intégré dans le tableau de bord utilisateur (recherche serveur débouncée), en remplacement de l'ancien filtre client limité aux titres

---

## [2.0.0] - 2026-07-07

### Ajouté
- Journal des décisions RAG (`docs/E3/RAG_DECISIONS_LOG.md`)
- Lint Python automatisé (Ruff) dans la CI
- Rate limiting sur `POST /login` (5/min par IP) et `POST /ask/stream` (20/min par compte utilisateur) via `slowapi`
- Tests de composants frontend : `UserDashboard`, `SavDashboard`, `AdminDashboard`

### Modifié
- `GET /v1/me/export` (export RGPD Art. 15/20) renvoie désormais un PDF au lieu d'un JSON — **rupture de contrat** pour tout consommateur qui parsait la réponse JSON
- `backend/db/init-db.sql` resynchronisé avec `models.py` (schéma complet dès l'installation, plus besoin d'attendre les migrations au démarrage)
- Dépendances Python unifiées dans `backend/pyproject.toml` (suppression de `requirements.txt`/`requirements-dev.txt`)

### Sécurité
- `POST /v1/setup-admin` — **rupture de contrat** : endpoint auparavant accessible sans authentification, désormais désactivé par défaut et protégé par header `X-Setup-Key`

### Retiré
- Fichiers polluants versionnés par erreur (index pgvector binaire, lock LibreOffice, lockfiles pnpm), code mort (`ingest_pdf.py`, `migrate.py`, `uv.lock`), dépendance frontend inutilisée `react-is`

---

## [1.0.0] - 2026-05-18

### Ajouté

**Backend (FastAPI)**
- API REST complète (25 endpoints) organisée en 7 routers : authentification, sessions, messages, IA, base de connaissances, utilisateurs, analytics
- Pipeline RAG : vectorisation via Mistral-embed (1024 dimensions), recherche cosinus HNSW sur pgvector, prompt enrichi contextuellement
- Streaming des réponses IA token par token (`StreamingResponse`)
- Transfert de session vers agent humain avec raisons catégorisées (technique / complexe / sensible / autre)
- Clôture de session avec résumé IA automatique et indexation du transcript dans la base de connaissances
- Feedback utilisateur sur les réponses IA (pouce haut / pouce bas)

**Base de données**
- Schéma PostgreSQL avec extension pgvector : 6 tables (`roles`, `utilisateur`, `chat_sessions`, `chat_messages`, `ai_call_logs`, `knowledge_base`)
- Index HNSW cosinus sur `knowledge_base.embedding`
- Migrations incrémentales au démarrage de l'application (idempotentes)

**Sécurité & RGPD**
- RBAC à 3 rôles (user, sav, admin) avec vérification d'ownership sur chaque ressource
- JWT HS256 + cookie HttpOnly SameSite=strict (double authentification : Bearer ou cookie)
- Mots de passe hashés bcrypt, absents de toutes les réponses API
- Soft-delete sur `utilisateur` et `chat_sessions` (colonne `deleted_at`)
- Purge automatique RGPD des données supprimées après 30 jours (APScheduler, cron 03:00 UTC)
- Export des données personnelles — droit d'accès et portabilité (Art. 15 & 20 RGPD) via `GET /v1/me/export`

**Ingestion de la base de connaissances**
- Scraping web avec respect du robots.txt, résolution de sitemap XML (2 niveaux), filtre domaine
- Ingestion de fichiers PDF, DOCX et TXT
- Pipeline de nettoyage : suppression null bytes / caractères de contrôle, détection contenu binaire, normalisation espaces, longueur minimale 80 caractères
- Chunking sémantique : `RecursiveCharacterTextSplitter` (1 000 c / overlap 100 c, max 80 chunks par ingestion)
- Embedding par batchs (`EMBED_BATCH_SIZE=12`) pour éviter les timeouts API

**Monitoring & Analytics**
- Table `ai_call_logs` : latence, chunks RAG trouvés, succès/erreur, modèle utilisé
- Dashboard analytics : taux de résolution IA, satisfaction (feedback), raisons de transfert, agents SAV
- Dashboard monitoring IA : latence moyenne, taux d'erreur, qualité RAG (`no_context_rate`), KB Health Score
- Alertes calculées avec seuils warning/critical sur 5 métriques
- Comparaison période courante / période précédente sur les métriques IA

**Frontend (Next.js 15)**
- Interface de chat avec streaming temps réel
- Historique paginé des conversations dans la sidebar
- Dashboard Tableau de bord (utilisateur)
- Dashboard Analytics (admin/sav) avec graphiques Recharts
- Dashboard Monitoring IA (admin/sav)
- Espace gestion de la base de connaissances (admin/sav)
- Page de paramètres (profil, changement de mot de passe)
- Landing page publique
- Pages authentification (connexion, inscription) avec indicateur de robustesse du mot de passe
- Thème cohérent indigo, design responsive

**Infrastructure**
- Docker : Dockerfile backend et frontend, docker-compose orchestrant 7 services (backend, frontend, PostgreSQL+pgvector, Redis, pgAdmin, Ollama, Open WebUI)
- CI GitHub Actions : lint TypeScript, ESLint, tests Pytest avec couverture, build Next.js — déploiement Render déclenché si tout passe
- Déploiement automatique sur Render (backend + frontend + base PostgreSQL managée)

### Modifié
- Initialisation automatique des rôles et du compte admin au démarrage (variables d'environnement `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`)

---

[2.10.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.10.0
[2.9.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.9.0
[2.8.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.8.0
[2.7.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.7.0
[2.6.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.6.0
[2.5.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.5.0
[2.4.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.4.0
[2.3.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.3.0
[2.2.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.2.0
[2.1.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.1.0
[2.0.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v2.0.0
[1.0.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v1.0.0
