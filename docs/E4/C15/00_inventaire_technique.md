# Inventaire technique — SmartTicket (source de vérité C15)

> Généré par exploration du code source le 2026-05-08. Toutes les valeurs sont lues dans les fichiers — aucune n'est inventée.

---

## 1. Structure du dépôt

```
PFE_ECE/
├── backend/            FastAPI + SQLAlchemy + Mistral client
├── frontend/           Next.js 16 (React 19)
├── docs/               Documentation projet
├── data/               Volumes persistants (postgres, redis, ollama)
├── ollama/             Script d'initialisation Ollama (dev)
├── docker-compose.yml  Orchestration locale (7 services)
├── render.yaml         Déploiement Render.com (2 services + 1 DB)
└── .github/workflows/  Pipeline CI/CD (ci.yml)
```

**Architecture effective** : 2 services applicatifs déployés (backend monolith + frontend), 1 base de données managée (PostgreSQL + pgvector). Pas de microservices séparés.

---

## 2. Stack frontend — `frontend/package.json`

| Lib | Version | Rôle |
|---|---|---|
| next | ^16.1.6 | Framework React SSR/SSG |
| react | 19.2.3 | UI library |
| react-dom | 19.2.3 | DOM renderer |
| typescript | ^5 | Typage statique |
| tailwindcss | ^4 | CSS utilitaire |
| @radix-ui/react-dialog | ^1.1.15 | Modaux accessibles |
| @base-ui/react | ^1.0.0 | Composants UI base |
| radix-ui | ^1.4.3 | Suite composants primitifs |
| lucide-react | ^0.562.0 | Icônes SVG |
| recharts | ^3.6.0 | Graphiques (dashboard analytics) |
| shadcn | ^3.6.3 | Générateur de composants UI |
| streamdown | ^2.4.0 | Rendu Markdown en streaming |
| clsx | ^2.1.1 | Utilitaire classes CSS |
| class-variance-authority | ^0.7.1 | Variants de composants |
| tailwind-merge | ^3.4.0 | Fusion de classes Tailwind |
| tw-animate-css | ^1.4.0 | Animations CSS Tailwind |

**Frameworks de test frontend** : jest ^29, @testing-library/react ^16, ts-jest ^29, jest-environment-jsdom ^29

---

## 3. Stack backend — `backend/requirements.txt`

| Lib | Version (spécifiée) | Rôle |
|---|---|---|
| fastapi | latest | Framework API REST async |
| uvicorn | latest | Serveur ASGI |
| sqlalchemy | latest | ORM Python |
| psycopg2-binary | latest | Driver PostgreSQL |
| pgvector | latest | Extension PostgreSQL pour vecteurs |
| passlib[bcrypt] | latest | Hachage mots de passe |
| bcrypt | 4.0.1 | Backend bcrypt (épinglé) |
| python-jose[cryptography] | latest | JWT (HS256) |
| email-validator | >=2.0.0 | Validation email Pydantic |
| python-dotenv | latest | Chargement .env |
| requests | latest | Client HTTP (appels Mistral API) |
| ollama | latest | Client Ollama (non utilisé en prod — legacy) |
| langchain-community | latest | Scraping/splitting documents |
| beautifulsoup4 | latest | Parsing HTML |
| langchain-text-splitters | latest | Découpage de texte en chunks |
| chromadb | latest | Base vectorielle (legacy — remplacée par pgvector) |
| lxml | 6.0.2 | Parser XML/HTML |
| pypdf | 6.9.2 | Lecture PDF |
| python-docx | 1.2.0 | Lecture DOCX |
| typing-extensions | 4.15.0 | Compatibilité types Python |

**Frameworks de test backend** : pytest, pytest-cov, httpx

**Dépendances obsolètes constatées** :
- `chromadb` — présent dans requirements.txt mais remplacé par pgvector en prod
- `ollama` — présent mais le client actif est `mistral_client.py` (Mistral API)

---

## 4. Services Docker — `docker-compose.yml`

| Service | Image | Port(s) | Environnement |
|---|---|---|---|
| backend | ./backend/Dockerfile (python:3.11-slim) | 8000 | DATABASE_URL, SECRET_KEY, CORS_ORIGINS |
| frontend | ./frontend/Dockerfile (node:20-slim) | 3005 | NEXT_PUBLIC_API_URL |
| postgres | pgvector/pgvector:pg16 | 5432 | POSTGRES_DB=ticketdb, POSTGRES_USER=admin |
| redis | redis:7-alpine | 6379 | — |
| pgadmin | dpage/pgadmin4 | 5050 | (outil admin, dev uniquement) |
| ollama | ollama/ollama:latest | 11434 | (LLM local, dev uniquement) |
| ollama-webui | ghcr.io/open-webui/open-webui:main | 3002 | OLLAMA_BASE_URL |

**Note** : Redis est présent dans docker-compose.yml mais aucun client Redis n'est instancié dans le code backend actuel. Il était prévu pour la mise en cache des sessions mais n'a pas été connecté.

---

## 5. Services déployés en pré-production — `render.yaml`

| Service | Hébergeur | Type | Plan |
|---|---|---|---|
| pfe-ece-backend | Render.com | Docker Web Service | Free |
| pfe-ece-frontend | Render.com | Docker Web Service | Free |
| pfe-ece-postgres | Render.com | PostgreSQL managé | Free |

Redis **non déployé** en pré-production. Ollama **non déployé** en pré-production (Mistral API cloud utilisé à la place).

---

## 6. Modèles IA utilisés — `backend/mistral_client.py` + `backend/dependencies.py`

| Modèle | Usage | Variable d'env |
|---|---|---|
| `mistral-small-latest` | Génération de réponses (streaming) + résumés de sessions | `MISTRAL_MODEL` |
| `mistral-embed` | Vectorisation des questions et documents (1024 dimensions) | `EMBED_MODEL` |

API endpoint : `https://api.mistral.ai/v1` (configurable via `MISTRAL_API_URL`)

---

## 7. Endpoints API — `backend/routers/*.py` (tous préfixés `/v1`)

### Authentification (`auth.py`)
| Méthode | Chemin | Rôle |
|---|---|---|
| POST | /v1/register | Créer un compte (rôle user par défaut) |
| POST | /v1/login | Connexion → JWT + cookie httpOnly |
| POST | /v1/logout | Suppression du cookie |
| GET | /v1/me | Profil de l'utilisateur connecté |
| PUT | /v1/me | Modifier son profil |
| PUT | /v1/me/password | Changer son mot de passe |

### Sessions (`sessions.py`)
| Méthode | Chemin | Rôle |
|---|---|---|
| POST | /v1/sessions | Créer une session de chat |
| GET | /v1/sessions | Lister les sessions (par user_id) |
| DELETE | /v1/sessions/{id} | Supprimer une session |
| POST | /v1/sessions/{id}/close | Clore + générer résumé IA + indexer transcript |
| POST | /v1/sessions/{id}/transfer | Transférer vers agent humain |
| POST | /v1/sessions/{id}/resolve | Rétablir l'IA après transfert |
| GET | /v1/sessions/transferred | Lister les sessions en attente SAV |

### Messages (`messages.py`)
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | /v1/messages | Lister les messages d'une session |
| POST | /v1/messages | Envoyer un message |
| PATCH | /v1/messages/{id}/feedback | Note 👍/👎 sur une réponse IA |

### IA/RAG (`ai.py`)
| Méthode | Chemin | Rôle |
|---|---|---|
| POST | /v1/ask/stream | RAG + streaming Mistral (text/plain SSE) |

### Base de connaissances (`knowledge.py`)
| Méthode | Chemin | Rôle |
|---|---|---|
| POST | /v1/knowledge-base/ingest-url | Indexer une URL/sitemap (background task) |
| GET | /v1/knowledge-base/ingest-status | Statut d'un job d'ingestion |
| GET | /v1/knowledge-base/robots-check | Analyser robots.txt d'un domaine |
| GET | /v1/knowledge-base/sources | Lister les sources indexées |
| DELETE | /v1/knowledge-base/sources | Supprimer une source |
| POST | /v1/knowledge-base/ingest-file | Indexer un PDF/DOCX/TXT (background task) |

### Utilisateurs (`users.py`)
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | /v1/users | Lister les utilisateurs (admin/sav) |
| PUT | /v1/users/{id}/role | Modifier le rôle d'un utilisateur (admin) |
| PUT | /v1/users/{id} | Modifier un utilisateur (admin) |
| DELETE | /v1/users/{id} | Supprimer un utilisateur (admin) |

### Analytics (`analytics.py`)
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | /v1/analytics/stats | Statistiques IA (résolution, satisfaction, transferts, alertes) |

---

## 8. Schéma de base de données — `backend/models.py` + `backend/db/init-db.sql`

| Table | Colonnes clés | Notes |
|---|---|---|
| `roles` | id, nom_role (user/ai/sav/admin) | Table de référence |
| `utilisateur` | id, username, email, password_hash, prenom, nom, id_role, date_creation | id_role FK → roles |
| `chat_sessions` | id, id_utilisateur, title, status (open/transferred/closed), transfer_reason, date_creation | id_utilisateur FK → utilisateur CASCADE |
| `chat_messages` | id, id_session, type_envoyeur (user/ai/sav), contenu, feedback (1/-1/NULL), date_creation | id_session FK → chat_sessions CASCADE |
| `knowledge_base` | id, source_message_id, contenu, embedding vector(1024), category, source, date_creation | Index HNSW cosine_ops sur embedding |

Extension PostgreSQL activée : `vector` (pgvector), `pgcrypto`

---

## 9. Pipeline CI/CD — `.github/workflows/ci.yml`

Déclencheur : push/PR sur `master`

| Job | Étapes |
|---|---|
| backend-tests | checkout → setup Python 3.11 → pip install → pytest tests/ -v |
| frontend-tests | checkout → setup Node 20 → npm ci → tsc --noEmit → eslint → jest → npm run build |

Service PostgreSQL (pgvector/pgvector:pg15) instancié dans le runner CI pour les tests d'intégration backend.

---

## 10. Variables d'environnement requises — `.env.example`

| Variable | Valeur par défaut | Obligatoire |
|---|---|---|
| SECRET_KEY | change-me | Oui |
| ALGORITHM | HS256 | Non |
| ACCESS_TOKEN_EXPIRE_MINUTES | 60 | Non |
| DATABASE_URL | postgresql://admin:Password1234@postgres/ticketdb | Oui |
| CORS_ORIGINS | http://localhost:3005,http://localhost:3000 | Non |
| MISTRAL_API_KEY | (vide) | Oui |
| MISTRAL_API_URL | https://api.mistral.ai/v1 | Non |
| MISTRAL_MODEL | mistral-small-latest | Non |
| EMBED_MODEL | mistral-embed | Non |
| EMBEDDING_DIMENSION | 1024 | Non |
| MISTRAL_MAX_RETRIES | 5 | Non |
| KB_TOP_K | 4 | Non |
| KB_MAX_CONTEXT_CHARS | 3000 | Non |

---

## 11. Routes frontend — `frontend/app/`

| Route | Fichier | Rôle |
|---|---|---|
| / | (dashboard)/page.tsx | Tableau de bord (liste des sessions) |
| /ai-assistant/[id] | (chat)/ai-assistant/[id]/page.tsx | Interface de chat RAG |
| /analytics | (dashboard)/analytics/page.tsx | Dashboard analytics SAV/admin |
| /knowledge-base | (dashboard)/knowledge-base/page.tsx | Gestion base de connaissances |
| /settings | (dashboard)/settings/page.tsx | Paramètres utilisateur |
| /login | (auth)/login/page.tsx | Connexion |
| /sign-up | (auth)/sign-up/page.tsx | Inscription |
| /forgot-password | (auth)/forgot-password/page.tsx | Réinitialisation mot de passe |
| /api/ask | api/ask/route.ts | Proxy SSR vers /v1/ask/stream |

Toutes les routes `/api/*` sont proxifiées vers le backend via `next.config.ts` (`rewrites`).
