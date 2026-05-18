# Audit E3 — SmartTicket
## Bloc "Développement et intégration d'un modèle d'IA"

**Date de l'audit :** 2026-05-18
**Auditeur :** Claude Code (claude-sonnet-4-6)
**Périmètre :** SmartTicket, branche `main`

---

## Synthèse

| Compétence | Verdict | Effort restant |
|------------|---------|----------------|
| C9 — API REST exposant un modèle IA | ✅ VALIDÉ | ~4 h |
| C10 — Intégration API IA dans application | ✅ VALIDÉ | ~8 h |
| C11 — Monitoring du modèle IA | ⚠️ PARTIEL | ~8 h |
| C12 — Tests automatisés | ⚠️ PARTIEL | ~15 h |
| C13 — Chaîne de livraison continue | ⚠️ PARTIEL | ~6 h |

**Effort total estimé pour bloc E3 complet :** ~41 heures-homme

---

## C9 — Développer une API REST exposant un modèle IA

### ✅ Éléments validés

- Endpoint `POST /v1/ask/stream` expose Mistral AI (LLM) + pipeline RAG via REST (`backend/routers/ai.py:26-36`)
- Schema Pydantic `AskRequest` formalisé avec `Field(..., description=...)` sur chaque champ (`backend/schemas.py:158-162`)
- Documentation OpenAPI complète : `title`, `description`, `version`, tags par domaine (`backend/main.py:28-41`) — Swagger disponible sur `/docs`, ReDoc sur `/redoc`
- Streaming token-par-token via `StreamingResponse(media_type="text/plain")` (`backend/routers/ai.py:118`)
- Codes HTTP cohérents : 201 (register), 200, 400, 401, 403, 404 selon les cas (`backend/routers/auth.py:50`, `backend/routers/ai.py:42-49`)
- Gestion d'erreurs structurée : `try/except` + `raise HTTPException` dans `stream_tokens()` avec capture du type d'erreur (`backend/routers/ai.py:87-115`)
- Authentication JWT via `OAuth2PasswordBearer` et cookie `httpOnly` / `SameSite=strict` (`backend/dependencies.py:14`, `backend/routers/auth.py:81-84`)
- Contrôle d'accès RBAC : vérification `is_admin_or_sav()` ou propriété de session sur chaque route protégée (`backend/routers/ai.py:46`, `backend/dependencies.py:98-101`)
- Pipeline RAG exposé : embed query → recherche cosinus pgvector → prompt enrichi → génération LLM (`backend/routers/ai.py:60-74`)
- Mode `rag_only` pour inspecter le contexte brut sans appel LLM (`backend/routers/ai.py:76-80`)

### ⚠️ Éléments partiels

- **Schema de réponse streaming non formalisé** : `/ask/stream` n'a pas de `response_model` (sortie texte brut, non documentée dans l'OpenAPI) — `backend/routers/ai.py:26-36`

### ❌ Éléments manquants

- **Endpoint `/health` structuré** : seul `GET /` renvoie `{"status": "Online"}` sans état de la DB, de l'API Mistral ou de pgvector (`backend/main.py:183-185`)
- **Rate limiting** : aucun mécanisme de limitation des requêtes (pas de SlowAPI ou équivalent)

### Verdict
✅ VALIDÉ

### Effort pour atteindre 100 %
~4 heures — endpoint `/health` avec check DB + Mistral (2 h), rate limiting via SlowAPI (1 h), documenter la sortie streaming en OpenAPI (1 h)

---

## C10 — Intégrer une API d'IA dans une application

### ✅ Éléments validés

- Consommation complète de l'API Mistral : `chat/completions` (génération streaming + non-streaming) et `embeddings` (`backend/mistral_client.py:79-168`)
- `MISTRAL_API_KEY` externalisée en variable d'environnement, jamais en dur dans le code ; marquée `sync: false` sur Render (`backend/mistral_client.py:9-13`, `render.yaml:29`)
- Retry avec backoff exponentiel : 5 tentatives, délai configurable via `MISTRAL_BACKOFF_SECONDS` (`backend/mistral_client.py:46-76`)
- Gestion explicite du code HTTP 429 avec lecture de l'en-tête `Retry-After` (`backend/mistral_client.py:58-62`)
- Timeout configurable via `REQUEST_TIMEOUT` (env var, défaut 10 s) (`backend/dependencies.py:21`)
- Consommation correcte du stream SSE Mistral ligne par ligne avec parsing JSON robuste (`backend/mistral_client.py:120-137`)
- Interface utilisateur claire : chat streaming, suggestions de questions, toggle AI on/off, transfert vers agent humain (`frontend/app/(chat)/ai-assistant/[id]/page.tsx`)
- Accessibilité : `aria-label` sur les boutons de feedback ("Marquer comme bonne réponse", "Marquer comme mauvaise réponse") (`frontend/app/(chat)/ai-assistant/[id]/page.tsx:383,392`)
- `aria-live="polite"` et `aria-busy={isSending}` sur la zone de messages (`frontend/app/(chat)/ai-assistant/[id]/page.tsx:318`)
- `<label htmlFor="chat-input">` avec classe `sr-only` sur le champ de saisie (`frontend/app/(chat)/ai-assistant/[id]/page.tsx:467-471`)
- Route Next.js `/api/mistral-status` pour exposer le statut de l'API tierce en temps réel (`frontend/app/api/mistral-status/route.ts`)

### ⚠️ Éléments partiels

- **Fallback si Mistral indisponible** : en cas d'exception, le message `"Erreur IA pendant la génération."` est renvoyé et loggé dans `AICallLog`, mais aucune réponse de secours fonctionnelle n'est produite — `backend/routers/ai.py:92-98`
- **Accessibilité contraste / navigation clavier** : les classes Tailwind utilisées sont cohérentes (indigo-600 sur blanc), mais aucun test automatisé d'accessibilité ne valide les ratios de contraste ni la navigation clavier complète

### ❌ Éléments manquants

- **Fallback LLM secondaire / circuit breaker** : si Mistral est indisponible plusieurs minutes, aucun basculement automatique vers un LLM de repli ou une réponse statique issue de la KB
- **Tests d'accessibilité automatisés** : aucun test axe-core, Playwright a11y ou pa11y dans la CI

### Verdict
✅ VALIDÉ

### Effort pour atteindre 100 %
~8 heures — fallback KB statique ou message d'indisponibilité configuré (3 h), tests d'accessibilité automatisés avec axe-playwright (4 h), documentation des rate limits Mistral en commentaire de code (1 h)

---

## C11 — Monitorer un modèle IA

**RAPPEL : la boucle d'amélioration RAG remplace le fine-tuning sur ce projet.**
L'évaluation porte sur l'instrumentation de la boucle : collecte de métriques → analyse → action sur KB/paramètres → mesure d'impact.

### ✅ Éléments validés

- **Table dédiée `ai_call_logs`** avec colonnes : `latency_ms`, `rag_chunks_found`, `rag_context_chars`, `success`, `error_type`, `model_name`, `date_creation` (`backend/models.py:50-62`)
- **Logging systématique** de chaque appel IA dans le bloc `finally` du générateur `stream_tokens()` — aucun appel ne passe sans log (`backend/routers/ai.py:100-116`)
- **Endpoint `GET /v1/analytics/ai-metrics`** : latence moyenne, taux d'erreur, `avg_rag_chunks`, `no_context_rate`, tendance journalière, comparaison période précédente (`backend/routers/analytics.py:106-250`)
- **Endpoint `GET /v1/analytics/stats`** : taux de résolution IA, score de satisfaction (feedback +1/-1), taux de transfert humain, ventilation par raison de transfert (`backend/routers/analytics.py:54-103`)
- **Métriques qualité utilisateur** : feedback +1/-1 par message IA stocké en colonne `feedback` sur `chat_messages` ; `satisfaction_score` calculé dynamiquement (`backend/routers/analytics.py:82-84`)
- **Alertes calculées** pour 5 métriques avec niveaux `warning`/`critical` : résolution IA, satisfaction, taux de transfert, latence, taux d'erreur RAG (`backend/routers/analytics.py:15-51`, `routers/analytics.py:223-234`)
- **KB Health Score (0-100)** composé de `context_quality` (70 %) et `reliability` (30 %) (`backend/routers/analytics.py:216-221`)
- **Dashboard frontend `/monitoring`** : 4 KPIs avec comparaison période précédente, graphique latence journalière, alertes inline, status Mistral AI temps réel (`frontend/app/(dashboard)/monitoring/page.tsx`)
- **Recommandations auto d'amélioration** générées depuis les métriques (enrichir KB, réduire `KB_MAX_CONTEXT_CHARS`, vérifier API key) (`frontend/app/(dashboard)/monitoring/page.tsx:440-486`)
- **Historique enrichissements KB** visualisé sous forme de timeline avec marqueurs sur le graphique de latence (`frontend/app/(dashboard)/monitoring/page.tsx:557-627`)
- Boucle RAG instrumentée de bout en bout : les métriques permettent d'orienter le `KB_TOP_K`, `KB_MAX_CONTEXT_CHARS`, le seuil cosinus et la qualité des sources

### ⚠️ Éléments partiels

- **Alertes passives uniquement** : les alertes sont calculées et retournées dans le JSON des endpoints, puis affichées dans le dashboard — mais aucune notification active n'est envoyée (pas de mail, Slack, webhook) en cas de dépassement de seuil en production
- **Tokens consommés non tracés** : le champ `tokens_used` est absent de `AICallLog` (`backend/models.py:50-62`) — la consommation API Mistral n'est pas mesurable depuis les logs

### ❌ Éléments manquants

- **Alertes push actives** : aucun envoi email/Slack/webhook sur dépassement de seuil — les alertes ne déclenchent rien en dehors de l'affichage frontend
- **CHANGELOG ou journal de décisions RAG** : aucune trace des itérations (paramètres modifiés, sources ajoutées, impact mesuré) — l'historique n'existe que dans les données en base, pas dans un document consultable
- **Endpoint `/metrics` compatible Prometheus** : pas d'exposition de métriques au format OpenMetrics pour intégration dans Grafana/alertmanager

### Verdict
⚠️ PARTIEL

### Effort pour atteindre 100 %
~8 heures — alertes push via webhook configurable (3 h), ajout colonne `tokens_used` dans `AICallLog` + mise à jour du logging (1 h), CHANGELOG RAG avec template de décision (2 h), endpoint `/metrics` Prometheus basique (2 h)

---

## C12 — Tests automatisés

### ✅ Éléments validés

- **Dossier `backend/tests/`** avec 4 fichiers : `conftest.py`, `test_api.py`, `test_rag_evaluation.py`, `test_utils.py` (`backend/tests/`)
- **`pytest.ini`** configuré : `testpaths = tests`, `addopts = -v --tb=short` (`backend/pytest.ini:1-3`)
- **`conftest.py`** : DB de test PostgreSQL séparée, garde anti-corruption (`"test" not in TEST_DB_URL` → `RuntimeError`), isolation TRUNCATE avant chaque test, fixtures `client`, `auth_client`, `db_session` (`backend/tests/conftest.py:10-16`, `conftest.py:56-60`)
- **Tests sur la préparation des données** : `chunk_text` (taille max, overlap, edge cases), `sanitize_text` (null bytes, whitespace), `sanitize_model_name` (`backend/tests/test_utils.py`)
- **Tests sur le pipeline RAG** : retrieval document pertinent, fallback KB vide, priorité cosinus, multi-documents, construction du prompt (sections CONTEXTE/QUESTION, fallback vide) (`backend/tests/test_rag_evaluation.py`)
- **Tests d'intégration API** : register (succès, duplicate email, duplicate username), login (succès, mauvais mot de passe), `GET /me` (auth, profil), sessions (création, listing, isolation RBAC) (`backend/tests/test_api.py`)
- **`requirements-dev.txt`** présent : `pytest`, `pytest-cov`, `httpx` (`backend/requirements-dev.txt`)
- **CI exécute pytest** avec couverture (`--cov=. --cov-report=term-missing --cov-report=xml`) + jest + TypeScript check + ESLint (`.github/workflows/ci.yml:52-56`, `ci.yml:108-119`)
- **Frontend** : `jest.config.js`, `__tests__/utils.test.ts` (tests sur `cn()`), `__tests__/api.test.ts` (validations locales)

### ⚠️ Éléments partiels

- **Tests frontend insuffisants** : `api.test.ts` ne teste que des chaînes de caractères statiques en local (pas de mock `fetch`, pas d'appel à la route `/api/ask`) — `frontend/__tests__/api.test.ts:8-34`
- **Couverture sans seuil minimum** : la CI génère `coverage.xml` mais ne bloque pas si la couverture descend sous un seuil (pas de `--cov-fail-under`) — `.github/workflows/ci.yml:52-56`

### ❌ Éléments manquants

- **Tests sur les endpoints analytics** : `GET /v1/analytics/stats` et `GET /v1/analytics/ai-metrics` ne sont pas testés
- **Tests sur les endpoints knowledge-base** : `POST /knowledge-base/ingest-url`, `POST /knowledge-base/ingest-file`, `GET /knowledge-base/sources` ne sont pas testés
- **Évaluation LLM automatisée** : pas de framework RAGAS, G-Eval ou benchmark custom mesurant la pertinence/fidélité des réponses générées — le `test_rag_evaluation.py` valide le retrieval mais pas la qualité de génération
- **Jeux de données dédiés** : pas de dataset question/réponse de référence pour l'évaluation qualité
- **Tests E2E** : aucun Playwright ni Cypress testant les flux utilisateur complets (login → chat → feedback)

### Verdict
⚠️ PARTIEL

### Effort pour atteindre 100 %
~15 heures — tests analytics (3 h), tests knowledge-base avec mock ingest (3 h), tests frontend réalistes avec mock `fetch` (4 h), dataset Q/R + évaluation RAGAS minimaliste (5 h)

---

## C13 — Chaîne de livraison continue

### ✅ Éléments validés

- **Dockerfile backend** : `python:3.11-slim`, `libpq-dev`, `pip install -r requirements.txt`, `EXPOSE 8000`, CMD uvicorn avec `${PORT:-8000}` (`backend/Dockerfile`)
- **Dockerfile frontend** : `node:20-slim`, `npm ci`, `npm run build` prod, `EXPOSE 3005`, `${PORT:-3005}` (`frontend/Dockerfile`)
- **`docker-compose.yml`** orchestrant 7 services : backend, frontend, postgres (pgvector/pg16), redis, ollama, pgadmin, open-webui (`docker-compose.yml`)
- **CI GitHub Actions** avec 3 jobs séquencés : `backend-tests` → `frontend-tests` → `deploy` (ce dernier conditionné aux deux premiers) (`.github/workflows/ci.yml`)
- **ESLint** sur `app components hooks lib` avec `--max-warnings 0` dans la CI (`ci.yml:113-114`)
- **TypeScript check** `tsc --noEmit` dans la CI (`ci.yml:108-110`)
- **pytest avec couverture** XML dans la CI (`ci.yml:52-56`)
- **Build Next.js** de production vérifié dans la CI (`ci.yml:120-124`)
- **Déploiement automatique sur Render** via webhooks, déclenché uniquement sur push `main` après validation complète (`ci.yml:143-171`)
- **`render.yaml`** comme Infrastructure as Code pour les services et la base de données Render (`render.yaml`)
- **Artefacts CI** : `test-results.xml` et `coverage.xml` uploadés (`ci.yml:77-84`)
- **Environnement reproductible localement** : `docker compose up -d --build` suffit, DB initialisée par `init-db.sql`

### ⚠️ Éléments partiels

- **`requirements.txt` partiellement non versionné** : `fastapi`, `uvicorn`, `sqlalchemy`, `pgvector`, `requests` (×2, doublon), `beautifulsoup4`, `langchain-community`, `langchain-text-splitters` n'ont pas de version pinnée — reproductibilité non garantie (`backend/requirements.txt`)
- **`uv.lock` présent mais non utilisé en CI** : le lockfile `uv.lock` existe dans le repo, mais la CI utilise `pip install -r requirements.txt` et non `uv sync` — le lockfile est décoratif (`.github/workflows/ci.yml:49`)
- **Pas de lint Python dans la CI** : ESLint est présent pour le frontend, mais aucun ruff/flake8/pylint ne tourne sur le backend

### ❌ Éléments manquants

- **Aucun tag Git SemVer** : `git tag --list` vide — aucune stratégie de versionnage des releases
- **Aucun CHANGELOG** : pas de `CHANGELOG.md` ni de `CHANGELOG.rst` dans le repo
- **Lint Python absent de la CI** : ruff ou flake8 ne tournent pas en CI — qualité du code backend non enforced automatiquement
- **Pas de build/push Docker vers un registry** : le déploiement Render utilise `runtime: docker` avec build à la volée — pas de publication vers GHCR, ECR ou DockerHub
- **Pas de scanning de vulnérabilités** : aucun Trivy, Snyk, ou Dependabot pour les dépendances Python et npm

### Verdict
⚠️ PARTIEL

### Effort pour atteindre 100 %
~6 heures — lint Python ruff dans CI (1 h), pinning complet `requirements.txt` + migration CI vers `uv sync` (1 h), SemVer avec premier tag + CHANGELOG template (2 h), scanning Trivy basique en CI (2 h)

---

## Plan d'action recommandé

Liste priorisée du plus bloquant au moins bloquant pour valider E3 complet :

1. **Tests analytics + knowledge-base** — 6 h — impact direct C12 (coverage manquante sur les endpoints métier les plus importants)
2. **Alertes push actives** (webhook/email) — 3 h — impact C11 (critère explicite du référentiel ; les alertes passives ne suffisent pas)
3. **CHANGELOG et journal de décisions RAG** — 2 h — impact C11 + C13 (trace de la boucle d'amélioration itérative et du versionnage)
4. **SemVer + premier tag Git** — 1 h — impact C13 (critère versionnage explicite)
5. **Lint Python (ruff) dans la CI** — 1 h — impact C13 (parité avec le lint frontend déjà présent)
6. **Tests frontend réalistes** (mock fetch, vrais composants) — 4 h — impact C12 (les tests actuels ne valident aucun comportement React)
7. **Pinning complet requirements.txt** — 1 h — impact C13 (reproductibilité build)
8. **Endpoint `/health` structuré** (DB + Mistral) — 2 h — impact C9 (bonne pratique observabilité)
9. **Champ `tokens_used` dans `AICallLog`** — 1 h — impact C11 (métriques de coût API Mistral)
10. **Fallback si Mistral indisponible** — 3 h — impact C10 (résilience production)
11. **Jeux de données Q/R + évaluation RAGAS minimaliste** — 5 h — impact C12 (évaluation qualité RAG automatisée)

---

## Annexes

### Fichiers consultés

```
README.md
backend/main.py
backend/dependencies.py
backend/mistral_client.py
backend/models.py
backend/schemas.py
backend/database.py (non lu intégralement — structure standard SQLAlchemy)
backend/requirements.txt
backend/requirements-dev.txt
backend/pytest.ini
backend/Dockerfile
backend/routers/ai.py
backend/routers/analytics.py
backend/routers/auth.py
backend/routers/knowledge.py
backend/routers/messages.py (non lu — hors périmètre audit IA)
backend/routers/sessions.py (non lu — hors périmètre audit IA)
backend/routers/users.py (non lu — hors périmètre audit IA)
backend/tests/conftest.py
backend/tests/test_api.py
backend/tests/test_rag_evaluation.py
backend/tests/test_utils.py
backend/tests/__init__.py
backend/uv.lock (existence vérifiée, non lu)
frontend/Dockerfile
frontend/package.json
frontend/jest.config.js (existence vérifiée)
frontend/app/(chat)/ai-assistant/[id]/page.tsx
frontend/app/(dashboard)/monitoring/page.tsx
frontend/app/(dashboard)/analytics/page.tsx (existence vérifiée, non lu)
frontend/app/api/ask/route.ts (existence vérifiée)
frontend/app/api/mistral-status/route.ts
frontend/__tests__/api.test.ts
frontend/__tests__/utils.test.ts
.github/workflows/ci.yml
docker-compose.yml
render.yaml
docs/E3/ (existence vérifiée)
```

Recherche globale de CHANGELOG : aucun fichier trouvé.
Recherche de tags Git : `git tag --list` → vide.

### Hypothèses

- **"Modèle IA"** au sens E3 est interprété comme le système complet (Mistral API + pipeline RAG + base de connaissances), conformément au contexte du projet. Mistral AI est une API tierce non fine-tunée.
- **Amélioration itérative** : l'audit C11 évalue la boucle KB/paramètres RAG (KB_TOP_K, KB_MAX_CONTEXT_CHARS, qualité sources) comme équivalent fonctionnel du monitoring de modèle.
- `backend/database.py`, `routers/messages.py`, `routers/sessions.py`, `routers/users.py` n'ont pas été lus intégralement car ils ne sont pas au cœur des compétences E3 ; les interactions IA passant par ces couches sont couvertes via `routers/ai.py` et les tests d'intégration.
- L'accessibilité frontend ne peut être auditée à 100 % par lecture de code : les ratios de contraste réels dépendent du rendu CSS final (non évalué ici).
