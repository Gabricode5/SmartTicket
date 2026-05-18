# Changelog

Toutes les évolutions notables de SmartTicket sont consignées ici.

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
Versioning : [Semantic Versioning](https://semver.org/lang/fr/)

## [Non publié]

### Ajouté
- Journal des décisions RAG (`docs/E3/RAG_DECISIONS_LOG.md`)
- Lint Python automatisé (Ruff) dans la CI

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
- Docker : Dockerfile backend et frontend, docker-compose orchestrant 7 services (backend, frontend, PostgreSQL, pgAdmin, Traefik, Watchtower, pgvector)
- CI GitHub Actions : lint TypeScript, ESLint, tests Pytest avec couverture, build Next.js — déploiement Render déclenché si tout passe
- Déploiement automatique sur Render (backend + frontend + base PostgreSQL managée)

### Modifié
- Initialisation automatique des rôles et du compte admin au démarrage (variables d'environnement `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`)

---

[1.0.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v1.0.0
