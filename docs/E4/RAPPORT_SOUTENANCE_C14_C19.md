# Rapport de Soutenance — SmartTicket
## RNCP Concepteur Développeur IA — Compétences C14 à C19

---

## C14 — Analyse du besoin & Spécifications fonctionnelles

### Preuves concrètes

| Artefact | Fichier | Contenu clé |
|---|---|---|
| Spécifications fonctionnelles | `docs/E4/C14/01_specifications_fonctionnelles.md` | 8 user stories US-01→US-08, critères d'acceptation, scénarios nominaux et alternatifs |
| Modélisation des données | `docs/E4/C14/02_modelisation_donnees.md` | MCD Merise → MLD → MPD, diagrammes Mermaid + DDL SQL complet |
| Parcours utilisateurs | `docs/E4/C14/03_parcours_utilisateurs.md` | Flux client, opérateur SAV, administrateur — séquences de navigation |
| Accessibilité WCAG 2.1 AA | `docs/E4/C14/04_accessibilite.md` | 13 critères WCAG mappés aux 8 user stories (matrice de conformité) |
| Schéma BDD drawio | `docs/schema_bdd.drawio` | Schéma relationnel visuel (6 tables, clés étrangères, cardinalités) |
| Plan projet | `docs/Plan_Projet.xlsx` | Gantt (livrables, jalons, estimation charge) |

### Contenu des 8 User Stories

```
US-01 : Poser une question en langage naturel
US-02 : Recevoir une réponse augmentée par la base de connaissance (RAG)
US-03 : Escalader vers un opérateur humain
US-04 : Suivre l'état d'un ticket
US-05 : Opérateur SAV reprend la conversation
US-06 : Donner un feedback sur la réponse IA (👍 / 👎)
US-07 : Admin gère la base de connaissance (URL, PDF, DOCX, TXT)
US-08 : Admin consulte le tableau de bord analytique
```

### Étude de faisabilité IA

Documentée dans `docs/E4/C15/04_poc_preproduction.md` :
- Choix Mistral API vs self-hosted Ollama (coût/qualité/latence)
- Validation RAG sur corpus test avant déploiement
- Contraintes RGPD sur les données de conversation transmises à l'API externe

### Captures à inclure dans le slide

- **Slide C14-1** : Tableau des 8 user stories avec colonnes "Acteur / Action / Bénéfice / Critères d'acceptation"
- **Slide C14-2** : Diagramme MCD Merise (depuis `02_modelisation_donnees.md` ou `schema_bdd.drawio`)
- **Slide C14-3** : Matrice WCAG — 13 critères × statut (✅/⚠️) depuis `04_accessibilite.md`
- **Slide C14-4** : Parcours utilisateur principal (US-01 → US-02 → US-06)

### 3 bullet points clés

1. **8 user stories couvrant 3 profils** (client, SAV, admin) avec critères d'acceptation mesurables et scénarios d'échec documentés
2. **Modélisation complète Merise** — MCD → MLD → MPD avec intégration de la contrainte IA (table `knowledge_base` avec colonne `embedding vector(1024)`)
3. **Conformité WCAG 2.1 AA** dès la conception : 13 critères tracés (aria-live, focus-ring, contraste 4.5:1, reflow 320px) intégrés dans les critères d'acceptation des US

### Démo possible

> Montrer la page `/sign-up` : labels explicites, messages d'erreur `aria-describedby`, navigation clavier Tab→Enter, indicateur de focus visible — illustre la traçabilité US-01 → WCAG 2.1 AA critère 3.3.1

---

## C15 — Conception du cadre technique & Architecture

### Preuves concrètes

| Artefact | Fichier | Contenu clé |
|---|---|---|
| Inventaire technique | `docs/E4/C15/00_inventaire_technique.md` | Matrice stack complet : 30+ bibliothèques versionnées, justifications |
| Spécifications techniques | `docs/E4/C15/01_specifications_techniques.md` | Architecture BFF monolithique, 25 endpoints `/v1/*`, sécurité JWT+RBAC |
| Diagrammes flux données | `docs/E4/C15/02_diagramme_flux_donnees.md` | Diagramme C4 container + flux données (user → chat → RAG → Mistral → KB) |
| Éco-responsabilité | `docs/E4/C15/03_eco_responsabilite.md` | Estimation empreinte carbone, choix techniques durables |
| PoC pré-production | `docs/E4/C15/04_poc_preproduction.md` | Résultats PoC, critères de passage prod, limites identifiées |
| Log décisions RAG | `docs/E3/RAG_DECISIONS_LOG.md` | 6 ADR (Architecture Decision Records) IA avec signaux, décisions, impacts |

### Architecture Decision Records (ADR) — RAG

```
ADR-01 : Chunk size 1 000 chars / overlap 100
         → Signal : fragmentation à 500 chars
ADR-02 : Max 80 chunks par ingestion
         → Signal : qualité dégradée au-delà
ADR-03 : Filtrage binaire (images) avant embedding
         → Signal : pollution des embeddings
ADR-04 : Soft-delete pour conformité RGPD 30j
         → Signal : conflit retention vs suppression immédiate
ADR-05 : Table ai_call_logs pour monitoring qualité
         → Signal : absence de métriques qualité RAG
ADR-06 : Respect robots.txt avant ingestion URL
         → Signal : erreurs 403 sur URLs protégées
```

### Choix de stack — Justifications clés

| Choix | Alternatif écarté | Raison |
|---|---|---|
| FastAPI (Python) | Django REST | Performance async native, typing Pydantic, écosystème IA (LangChain) |
| Next.js 16 App Router | React SPA | SSR/ISR, routage serveur, proxy SSE natif |
| PostgreSQL + pgvector | ChromaDB | Unified storage (relationnel + vectoriel), ACID, backup managé |
| Mistral API | Ollama self-hosted | Qualité embeddings 1024-d, latence, absence GPU en prod |
| Render.com | AWS/GCP | Déploiement IaC (`render.yaml`), free tier, PostgreSQL managé |

### Captures à inclure dans le slide

- **Slide C15-1** : Diagramme C4 container (depuis `02_diagramme_flux_donnees.md`)
- **Slide C15-2** : Flux RAG détaillé : User → Next.js → FastAPI → pgvector → Mistral → SSE stream
- **Slide C15-3** : Tableau stack technique (depuis `00_inventaire_technique.md`)
- **Slide C15-4** : Un ADR complet (ex : ADR-01 chunk size) — format Signal/Décision/Conséquences

### 3 bullet points clés

1. **Architecture BFF monolithique justifiée** : Next.js sert de Backend-for-Frontend (proxy SSE `/api/ask` → `/v1/ask/stream`), évitant l'exposition directe du backend et simplifiant la gestion des tokens JWT via cookies httpOnly
2. **6 ADR documentés** pour les décisions IA/RAG critiques (chunking, filtrage, monitoring) — chaque décision avec signal déclencheur, métriques de validation et pistes V2
3. **pgvector comme ADR architectural majeur** : remplacement de ChromaDB (dépendance retirée) au profit d'un stockage unifié relationnel+vectoriel avec index HNSW cosinus sur 1024 dimensions

### Démo possible

> Montrer le fichier `docs/E3/RAG_DECISIONS_LOG.md` en live : lire l'ADR-01 (chunk size), expliquer comment le signal (fragmentation) a conduit à la décision, puis montrer la ligne correspondante dans `backend/ingest_postgres.py` (`chunk_size=1000, chunk_overlap=100`)

---

## C16 — Coordination Agile & MLOps

### Preuves concrètes

| Artefact | Fichier | Contenu clé |
|---|---|---|
| Versioning sémantique | `CHANGELOG.md` | v1.0.0 (2026-05-18), format Keep a Changelog, 25 endpoints livrés |
| Plan projet (Gantt) | `docs/Plan_Projet.xlsx` | Jalons, sprints, estimations charge |
| Monitoring IA | `backend/routers/analytics.py` | `/v1/analytics/ai-metrics` : latence, taux erreur, pertinence RAG |
| Table monitoring | `backend/db/init-db.sql` | `ai_call_logs` : latency_ms, chunks_found, success/error, timestamp |
| Dashboard monitoring | `frontend/app/(dashboard)/monitoring/page.tsx` | 5 métriques avec seuils warning/critical |
| Log décisions | `docs/E3/RAG_DECISIONS_LOG.md` | Traçabilité des itérations RAG (décisions V1 + 5 pistes V2) |
| Audit E3 | `docs/E3/AUDIT_E3.md` | Bilan déploiement, monitoring, versioning |

### Pipeline MLOps implicite

```
Ingestion → Chunking → Embedding (Mistral-embed) → pgvector
     ↓              ↓                  ↓
  robots.txt    ADR-01/02        dimension 1024
  compliance    (chunk/overlap)  HNSW cosinus

Inférence : RAG retrieval → Mistral-small-latest → SSE stream
     ↓
ai_call_logs → analytics/ai-metrics → dashboard alertes
```

### Métriques MLOps trackées

| Métrique | Seuil Warning | Seuil Critical | Source |
|---|---|---|---|
| Latence moyenne (ms) | 2 000 | 5 000 | `ai_call_logs.latency_ms` |
| Taux d'erreur (%) | 5 | 15 | `ai_call_logs.success` |
| Chunks trouvés (moyenne) | < 2 | < 1 | `ai_call_logs.chunks_found` |
| Score de pertinence KB | < 70 | < 50 | calculé dashboard |
| Fiabilité IA | < 85 | < 70 | calculé dashboard |

### Modèles versionnés (API-managed)

```python
# backend/mistral_client.py
MISTRAL_MODEL  = "mistral-small-latest"   # génération
EMBED_MODEL    = "mistral-embed"           # embeddings 1024-d
```

> Note : pas de MLflow/DVC (modèles hébergés via API Mistral), mais versioning indirect via `model_name` loggé dans `ai_call_logs` — permet de tracer les changements de modèle sur la qualité.

### Captures à inclure dans le slide

- **Slide C16-1** : Dashboard monitoring (capture `/monitoring`) avec les 5 alertes de seuils
- **Slide C16-2** : Diagramme pipeline MLOps (Ingestion → Chunking → Embedding → Retrieval → Génération → Monitoring)
- **Slide C16-3** : Table `ai_call_logs` schema + exemple requête SQL d'agrégation
- **Slide C16-4** : `CHANGELOG.md` — extrait v1.0.0 (liste des livrables du sprint final)

### 3 bullet points clés

1. **Monitoring qualité RAG en production** : chaque appel IA est loggé (`latency_ms`, `chunks_found`, `success`) avec 5 métriques calculées en temps réel et alertes visuelles warning/critical sur le dashboard admin
2. **Traçabilité des décisions d'amélioration** : le `RAG_DECISIONS_LOG.md` documente 6 itérations de tuning (chunk size, filtrage, soft-delete) avec signal déclencheur et impact mesuré — équivalent fonctionnel d'un experiment tracker
3. **Versioning sémantique des livrables** : CHANGELOG v1.0.0 trace l'ensemble des 25 endpoints et fonctionnalités livrés, avec tag git `v1.0.0` posé en production

### Démo possible

> Live sur `/monitoring` : montrer les métriques en temps réel, expliquer le calcul du "Score Santé KB" (70% contexte + 30% fiabilité), puis faire une requête RAG et observer l'enregistrement dans `ai_call_logs` via pgAdmin (`/5050`)

---

## C17 — Développement des composants & Conformité

### Preuves concrètes

| Artefact | Fichier | Contenu clé |
|---|---|---|
| API REST complète | `backend/routers/` | 25 endpoints `/v1/*` (7 routeurs), Swagger auto `/docs` |
| Sécurité auth | `backend/dependencies.py` | JWT HS256, bcrypt, RBAC 4 rôles, sanitize_text |
| Conformité RGPD | `backend/main.py` | APScheduler purge job 3h UTC, soft-delete, retention 30j |
| Modèles ORM | `backend/models.py` | 6 tables avec `deleted_at`, ON DELETE CASCADE |
| Pipeline RAG | `backend/ingest_postgres.py` | Ingestion URL/PDF/DOCX/TXT, robots.txt, chunking, embedding |
| Streaming IA | `backend/routers/ai.py` | SSE EventSourceResponse, RAG retrieval + Mistral stream |
| Interface chat | `frontend/app/(chat)/ai-assistant/[id]/page.tsx` | Streaming markdown, feedback UI, sessions |
| Dashboard analytics | `frontend/app/(dashboard)/analytics/page.tsx` | Recharts, KPIs, filtres admin/SAV |
| Accessibilité impl. | `docs/E4/C14/04_accessibilite.md` | aria-live, focus-ring, contraste, reflow 320px |

### Sécurité — Implémentation OWASP

```python
# backend/dependencies.py — JWT + RBAC
def get_current_user(token: str = Cookie(None), db = Depends(get_db)):
    # Validation JWT HS256, extraction user_id, vérification deleted_at
    ...

def is_admin_or_sav(current_user = Depends(get_current_user)):
    # Vérification rôle avant accès ressources admin
    ...

def sanitize_text(text: str) -> str:
    # Suppression null bytes + strip whitespace
    return text.replace('\x00', '').strip()
```

```python
# backend/main.py — RGPD purge automatique
@scheduler.scheduled_job("cron", hour=3, timezone="UTC")
async def purge_deleted_data():
    # Hard-delete utilisateurs/sessions soft-deleted > 30 jours
    cutoff = datetime.utcnow() - timedelta(days=30)
    ...
```

### Architecture de sécurité

```
Cookie httpOnly SameSite=strict
    ↓
JWT HS256 (SECRET_KEY env)
    ↓
RBAC : user | sav | admin  (is_admin_or_sav dependency)
    ↓
Pydantic v2 validation (schemas.py)
    ↓
sanitize_text() sur tous les inputs libres
    ↓
bcrypt passwords (passlib)
```

### RGPD — Flux de données

```
Utilisateur → données stockées localement (PostgreSQL Render)
           → transmises à Mistral API (requêtes seulement, non stockées)

Suppression :
  1. soft-delete (deleted_at = now())     → 30 jours
  2. purge job 3h UTC                     → hard-delete
  3. ON DELETE CASCADE → messages/sessions supprimés en cascade
```

### Captures à inclure dans le slide

- **Slide C17-1** : Swagger UI `/docs` — liste des 25 endpoints avec leurs schémas
- **Slide C17-2** : Interface chat en action (streaming, feedback 👍/👎, markdown rendu)
- **Slide C17-3** : Diagramme sécurité (Cookie → JWT → RBAC → Sanitization)
- **Slide C17-4** : Code du purge job RGPD dans `main.py` + schéma timeline retention 30j

### 3 bullet points clés

1. **Streaming SSE bout en bout** : de Mistral API → FastAPI `EventSourceResponse` → proxy Next.js `/api/ask` → composant React avec `streamdown` pour le rendu Markdown incrémental — architecture temps-réel sans WebSocket
2. **RGPD natif dans le schéma** : `deleted_at` sur `utilisateur` et `chat_sessions`, purge APScheduler automatique à 3h UTC, cascade SQL garantissant l'effacement complet — conformité traçable dès le DDL
3. **RBAC 4 niveaux** avec dépendances FastAPI injectées sur chaque route sensible, cookies httpOnly SameSite=strict éliminant les risques XSS sur les tokens

### Démo possible

> Démonstration du flux complet US-01→US-06 : login client → poser une question → voir le stream arriver token par token → donner un feedback 👎 → se connecter admin → voir le score de pertinence baisser dans analytics

---

## C18 — Intégration Continue & Tests automatisés

### Preuves concrètes

| Artefact | Fichier | Contenu clé |
|---|---|---|
| Workflow CI | `.github/workflows/ci.yml` | 3 jobs : backend-tests, frontend-tests, deploy (conditionnel) |
| Tests backend | `backend/tests/` | 4 fichiers + conftest.py : ~40 tests (auth, sessions, messages, analytics, RAG) |
| Tests frontend | `frontend/__tests__/` | 2 fichiers : api.test.ts, utils.test.ts |
| Config linting | `backend/pyproject.toml` | Ruff (E, W, F, I) — max-warnings: 0 |
| Config ESLint | `frontend/eslint.config.mjs` | TypeScript ESLint strict |
| Coverage pytest | CI artifact `coverage.xml` | pytest-cov XML + term-missing |
| Coverage Jest | CI output text-summary | --coverageReporters=text-summary |

### Workflow CI détaillé

```yaml
# .github/workflows/ci.yml

jobs:
  backend-tests:
    services:
      postgres:
        image: pgvector/pgvector:pg18   # DB réelle (pas de mock)
        env: POSTGRES_DB/USER/PASSWORD
    steps:
      - pip install -r requirements-dev.txt
      - ruff check . --select E,W,F,I    # Linting strict
      - pytest tests/ -v --tb=short
          --cov=. --cov-report=term-missing
          --cov-report=xml               # Artifact coverage
      - upload-artifact: coverage.xml, junit.xml

  frontend-tests:
    steps:
      - npm ci
      - tsc --noEmit                     # Type checking
      - eslint . --max-warnings 0        # Linting strict
      - npm test -- --watchAll=false
          --coverage --coverageReporters=text-summary
      - npm run build                    # Build validation

  deploy:
    needs: [backend-tests, frontend-tests]
    if: github.ref == 'refs/heads/main'  # CD conditionnel
    steps:
      - curl Render deploy hooks (backend + frontend)
```

### Couverture des tests backend

```
test_api.py         → Auth (register duplicat email/username, login, GET/PUT /me)
                    → Sessions (create, list, close, transfer, resolve)
                    → Messages (list, post, feedback)

test_analytics.py   → Auth 401/403 sur endpoints admin
                    → Structure réponse /stats + /ai-metrics
                    → Calcul métriques (latence, taux erreur)

test_rag_evaluation.py → Qualité RAG (pertinence, chunks trouvés)
                       → Évaluation embeddings Mistral

test_utils.py       → Fonctions utilitaires (sanitize_text, etc.)

conftest.py         → Fixtures : client, auth_client, registered_user, admin_client
```

### Captures à inclure dans le slide

- **Slide C18-1** : Capture GitHub Actions — pipeline CI vert (3 jobs checkmarks)
- **Slide C18-2** : Extrait `ci.yml` — les 3 jobs avec dépendances et conditions
- **Slide C18-3** : Output `pytest -v` avec liste des ~40 tests PASSED
- **Slide C18-4** : Output Ruff + ESLint "0 errors, 0 warnings" dans les logs CI

### 3 bullet points clés

1. **Pipeline CI 3 jobs** avec base de données PostgreSQL réelle en CI (service `pgvector:pg18`) — pas de mock, intégration testée dans les mêmes conditions qu'en production
2. **Double barrière qualité** : Ruff (lint Python, 0 warning toléré) + ESLint TypeScript strict + `tsc --noEmit` bloquants avant tout déploiement — la PR ne merge pas si le code ne compile pas proprement
3. **CD conditionnel** : le job `deploy` n'est déclenché que si `backend-tests` ET `frontend-tests` sont verts ET si le push est sur `main` — garantie que seul du code testé et lintérisé part en production

### Démo possible

> Montrer le dernier run GitHub Actions réussi, cliquer sur le job `backend-tests`, scroller jusqu'au résumé pytest (40 tests passed), puis sur la section Ruff ("All checks passed") — puis montrer comment un `ruff check` local échoue si on introduit une variable inutilisée

---

## C19 — Déploiement Continu & Livraison

### Preuves concrètes

| Artefact | Fichier | Contenu clé |
|---|---|---|
| IaC Render | `render.yaml` | 2 services Docker + 1 PostgreSQL managé (déclaratif) |
| Orchestration locale | `docker-compose.yml` | 7 services (dev + Ollama local) |
| Dockerfile backend | `backend/Dockerfile` | `python:3.11-slim`, port 8000 |
| Dockerfile frontend | `frontend/Dockerfile` | `node:20-slim`, build optimisé, port configurable `$PORT` |
| CD dans CI | `.github/workflows/ci.yml` | Deploy hooks Render déclenchés après tests verts |
| Migrations DB | `backend/db/init-db.sql` | DDL idempotent (`CREATE TABLE IF NOT EXISTS`, extensions) |
| Health check | `render.yaml` → `healthCheckPath: "/"` | Backend retourne `{"status": "Online"}` |

### Infrastructure as Code — render.yaml

```yaml
services:
  - type: web
    name: smartticket-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    healthCheckPath: /
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: smartticket-postgres
          property: connectionString
      - key: SECRET_KEY
        generateValue: true          # Auto-généré à la création
      - key: MISTRAL_API_KEY
        sync: false                  # Géré manuellement (secret)

  - type: web
    name: smartticket-frontend
    runtime: docker
    dockerfilePath: ./frontend/Dockerfile
    envVars:
      - key: NEXT_PUBLIC_API_URL
        value: https://smartticket-backend.onrender.com

databases:
  - name: smartticket-postgres
    plan: free
    databaseName: smartticket
    ipAllowList: []                  # Accès réseau interne uniquement
```

### Environnements

| Environnement | Stack | URL | Modèle IA |
|---|---|---|---|
| **Dev local** | docker-compose (7 services) | localhost:3005 | Ollama (local, GPU optional) |
| **Pre-prod / Prod** | Render IaC (render.yaml) | smartticket-frontend.onrender.com | Mistral API |

### Pipeline de déploiement complet

```
Git push → main
    ↓
GitHub Actions CI
    ├── backend-tests (PostgreSQL service pgvector:pg18)
    └── frontend-tests (tsc + eslint + jest + build)
    ↓ (si tous verts)
Job "deploy"
    ├── curl Render backend deploy hook
    └── curl Render frontend deploy hook
    ↓
Render Build
    ├── docker build (python:3.11-slim / node:20-slim)
    ├── docker push to Render registry
    └── docker run + health check "/"
    ↓
Migrations automatiques (startup FastAPI)
    └── init-db.sql exécuté au démarrage (idempotent)
```

### Captures à inclure dans le slide

- **Slide C19-1** : Diagramme pipeline complet (Git push → CI → Render deploy → health check)
- **Slide C19-2** : `render.yaml` complet annoté (IaC déclaratif, envVars, DB managée)
- **Slide C19-3** : `docker-compose.yml` — graphe des 7 services avec ports et dépendances
- **Slide C19-4** : Dashboard Render (captures deploy logs, statut services, DB metrics)

### 3 bullet points clés

1. **Infrastructure as Code 100% déclarative** : `render.yaml` définit 2 services Docker + PostgreSQL managé + variables d'environnement (dont auto-génération de `SECRET_KEY`) — un `git push` suffit à créer l'environnement from scratch
2. **Double environnement cohérent** : dev via `docker-compose.yml` (7 services dont Ollama local), prod via `render.yaml` (Mistral API) — le même Dockerfile est utilisé dans les deux contextes, garantissant la parité d'image
3. **Déploiement zéro-downtime automatisé** : les deploy hooks Render ne se déclenchent qu'après validation CI complète, avec health check sur `/` avant routage du trafic — rollback automatique Render si le health check échoue

### Démo possible

> Montrer le `render.yaml` en direct, expliquer le lien `fromDatabase.connectionString` (injection automatique), puis ouvrir le dashboard Render et montrer les logs du dernier déploiement (pull image → start → health check OK → live)

---

## Synthèse Transversale

### Matrice de couverture RNCP

| Compétence | Documentation | Code | Tests | CI/CD | Démo |
|---|---|---|---|---|---|
| **C14** | ✅ 4 docs + PDFs | ✅ Schéma DB | ✅ conftest fixtures | — | ✅ |
| **C15** | ✅ 5 docs + 6 ADR | ✅ Architecture BFF | — | — | ✅ |
| **C16** | ✅ CHANGELOG + log | ✅ ai_call_logs | ✅ test_analytics | — | ✅ |
| **C17** | ✅ specs + WCAG | ✅ 25 endpoints | ✅ test_api ~40 tests | ✅ CI bloquant | ✅ |
| **C18** | ✅ ci.yml | ✅ 4 fichiers tests | ✅ pytest + jest | ✅ 3 jobs | ✅ |
| **C19** | ✅ render.yaml | ✅ 2 Dockerfiles | — | ✅ CD conditionnel | ✅ |

### Points de vigilance pour la soutenance

> **C16** : Absence de MLflow/DVC — bien expliquer que les modèles sont gérés via API Mistral (versioning externe), compensé par le `ai_call_logs` comme substitute de tracking d'expériences.

> **C18** : Ne pas affirmer un taux de couverture exact sans l'avoir mesuré — préférer "couverture mesurée et reportée en CI via pytest-cov".

> **C19** : Render free tier = cold starts (~30s) et pas d'auto-scaling — reconnaître cette limite et mentionner la migration possible vers un tier payant ou une stack K8s en V2.

> **Fil rouge soutenance** : Chaque décision technique (ADR-01 à ADR-06) → problème observé → solution implémentée → code montrable — c'est le récit le plus fort.
