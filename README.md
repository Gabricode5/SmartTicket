# SmartTicket

SmartTicket est une plateforme de support client B2B2C : une entreprise cliente (le B2B) l'installe pour que **ses propres clients finaux** (le B2C — vos utilisateurs, sans compte préalable) puissent obtenir de l'aide via un assistant IA branché sur sa base de connaissances, avec transfert transparent vers un agent humain quand l'IA atteint ses limites.

## Pourquoi

Le support client se heurte souvent au même compromis : un chatbot générique qui ne connaît pas vraiment l'entreprise, ou une équipe humaine débordée par des questions répétitives. SmartTicket vise l'entre-deux : une IA qui répond en s'appuyant *uniquement* sur la documentation réelle de l'entreprise (RAG), avec un vrai filet de sécurité — transfert vers un agent SAV dès que la question sort du périmètre ou que le client le demande.

## Fonctionnalités

**Côté client final (public, B2C)**
- Chat IA sans compte préalable (visiteur anonyme) — la conversation peut être transformée en compte réel à tout moment sans rien perdre de l'historique
- Réponses générées par Mistral AI, contextualisées via une recherche vectorielle (pgvector) sur la base de connaissances de l'entreprise, avec reranking par pertinence + feedback utilisateur
- Transfert fluide vers un agent humain, avec le contexte de la conversation

**Côté équipe support (B2B)**
- Rôles à granularité fine : `user` (client), `sav` (agent), `superviseur` (gestion d'équipe), `admin`
- Dashboards Analytics & Monitoring IA (taux de résolution, latence, qualité de la base de connaissances), export PDF/CSV
- Recherche full-text dans l'historique des conversations
- Notifications in-app + email (réponse SAV, transfert de ticket)
- Base de connaissances alimentée par URL (scraping avec respect de `robots.txt`), fichiers (PDF/DOCX/TXT), avec recherche et filtres par catégorie
- Visite guidée à l'onboarding, adaptée au rôle de chaque utilisateur

**Sécurité & conformité**
- Authentification JWT, rate limiting sur les endpoints sensibles (login, inscription, chat)
- Guardrails anti prompt-injection sur le prompt système de l'IA
- RGPD : export des données personnelles (PDF), droit à l'effacement en cascade, purge automatique différée des comptes supprimés
- Colonne `tenant_id` posée en préparation d'une future bascule multi-tenant (architecture actuelle : une instance dédiée par client, cf. `ROADMAP.md`)

## Stack technique

| Couche | Techno |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, SQLAlchemy |
| Base de données | PostgreSQL + `pgvector` (recherche vectorielle) |
| IA | Mistral AI (génération de texte + embeddings) |
| Infra locale | Docker Compose |
| Déploiement | Render (cf. `render.yaml`) |

## Structure du dépôt

```text
frontend/   Interface utilisateur Next.js
backend/    API FastAPI, modèles, RAG et ingestion de la base de connaissances
docs/       Documents de projet
```

## Démarrer le projet

Voir [`INSTALLATION.MD`](./INSTALLATION.MD) pour le démarrage avec Docker Compose, les variables d'environnement, les services disponibles en local et le déploiement sur Render.

## Suivi du projet

L'avancement technique et fonctionnel (fait / en cours / à faire) est suivi dans [`ROADMAP.md`](./ROADMAP.md), et l'historique des changements dans [`CHANGELOG.md`](./CHANGELOG.md).
