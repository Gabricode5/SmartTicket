# Roadmap SmartTicket

Suivi des évolutions techniques et fonctionnelles du projet. Statuts : **Fait**, **En cours**, **À faire**.

## Fait

### Nettoyage (2026-07-07)
- [x] Suppression des fichiers polluants versionnés (index pgvector binaire, lock LibreOffice, lockfiles pnpm en double avec npm)
- [x] Suppression du code mort : `backend/ingest_pdf.py` (pipeline RAG jamais appelé), `backend/migrate.py` (doublonné par les migrations au démarrage), `backend/uv.lock` (orphelin, non utilisé)
- [x] Factorisation de `REASON_LABELS`/`REASON_COLORS`/`VALID_REASONS` dupliqués dans `backend/constants.py`
- [x] Remplacement des `print("DEBUG: ...")` par du `logging` cohérent (`routers/ai.py`, `ingest_postgres.py`)
- [x] Nettoyage de `requirements.txt` (doublon `requests`)
- [x] Suppression de la dépendance frontend inutilisée `react-is`
- [x] Nettoyage de `.claude/settings.local.json` (référence à un autre projet local)
- [x] Correction du tag OpenAPI vide sur le router `analytics`

### Sécurité (2026-07-07)
- [x] `POST /v1/setup-admin` sécurisé — était accessible sans authentification (création/promotion admin par n'importe qui). Désactivé par défaut, protégé par header `X-Setup-Key` + variable d'env `ADMIN_SETUP_KEY`

### Dette technique backend (2026-07-07)
- [x] `backend/db/init-db.sql` resynchronisé avec `models.py` — ajout de `utilisateur.deleted_at`, `chat_sessions.transfer_reason`/`deleted_at`, `chat_messages.feedback`, de la table `ai_call_logs` (absente), et de contraintes `NOT NULL` manquantes. Les `ALTER TABLE` au démarrage (`main.py`) sont conservés comme filet de sécurité pour les bases déjà déployées (ex: Render), mais ne sont plus nécessaires pour une installation neuve
- [x] Dépendances Python unifiées dans `backend/pyproject.toml` (`[project.dependencies]` + `[project.optional-dependencies].dev`) — suppression de `requirements.txt`/`requirements-dev.txt`. `Dockerfile` fait désormais `pip install .` et la CI fait `pip install "./backend[dev]"`

### Sécurité (2026-07-07)
- [x] Rate limiting sur `POST /login` (5/min par IP, anti brute-force) et `POST /ask/stream` (20/min par compte utilisateur, coûts Mistral) via `slowapi`. Stockage `memory://` par défaut (aucune dépendance externe requise) ; conçu pour basculer vers le Redis déjà présent dans `docker-compose.yml` (`RATE_LIMIT_STORAGE_URI=redis://...`) si l'app est un jour scalée sur plusieurs instances Render — **limite actuelle à connaître : sur une seule instance memory:// suffit, mais si le plan Render passe à plusieurs instances ce stockage local par instance ne suffira plus, il faudra alors activer Redis**. `Dockerfile` mis à jour avec `--proxy-headers` pour que l'IP détectée soit bien celle du client derrière le proxy Render, pas le load balancer

### Tests & CI (2026-07-07)
- [x] Tests de composants ajoutés pour `UserDashboard`, `SavDashboard`, `AdminDashboard` (25 tests, chargement/erreurs/recherche/actions clés type clôture de session, promotion SAV, envoi de réponse). Ajout de `frontend/jest.setup.ts` (matchers `@testing-library/jest-dom`, absents jusqu'ici) et `frontend/test-utils/fetchMock.ts` (mock `fetch` partagé). Suite complète vérifiée manuellement : `npm test`, `npx tsc --noEmit`, `npx eslint`, `npm run build` passent tous

### Fonctionnel / produit (2026-07-07)
- [x] Export RGPD (`GET /v1/me/export`) génère maintenant un vrai PDF au lieu d'un JSON téléchargé tel quel — nouveau module `backend/pdf_export.py` (`fpdf2`). Limite connue : les fonts core PDF (Helvetica) ne couvrent que le Latin-1, donc les emoji/caractères exotiques dans le contenu des messages utilisateurs sont remplacés par `?` plutôt que de faire planter l'export (compromis assumé plutôt que d'ajouter une police Unicode embarquée)

## En cours

_Rien en cours actuellement._

## À faire

### Sécurité
- [ ] Sortir le mot de passe DB par défaut `Password1234` du code source (actuellement codé en dur dans `database.py`, `docker-compose.yml`, `.env.example`)
- [ ] Revoir le rate limiting selon le plan Render retenu : si l'app tourne un jour sur plusieurs instances, basculer `RATE_LIMIT_STORAGE_URI` sur le Redis de `docker-compose.yml` (à provisionner aussi côté Render) pour un comptage partagé entre instances — `memory://` ne suffit qu'en mono-instance

### Dette technique backend
- [ ] Remplacer `@app.on_event("startup")` (déprécié) par `lifespan` FastAPI
- [ ] Remplacer `sqlalchemy.ext.declarative.declarative_base` (déprécié) par `sqlalchemy.orm.declarative_base`

### Tests & CI
- [ ] Ajouter un test de cohérence entre `init-db.sql` et `models.py` dans la CI

### Bugs découverts (pendant l'ajout des tests, 2026-07-07)
- [ ] `AdminDashboard.tsx` (colonne Conversations) imbrique un `<button>` "Clôturer" à l'intérieur du `<button>` de sélection de session — HTML invalide, React log une erreur d'hydratation (`<button> cannot be a descendant of <button>`). À corriger en remplaçant l'élément englobant par un `<div role="button">` (comme déjà fait dans `UserDashboard.tsx`) ou en sortant le bouton de clôture de l'élément cliquable

### Documentation
- [ ] Resynchroniser `docs/E3/RAG_DECISIONS_LOG.md` avec le code actuel (fonction renommée `chunk_quality_score`, formule du KB Health Score obsolète)
- [ ] Corriger `CHANGELOG.md` (mentionne Traefik/Watchtower, absents du `docker-compose.yml` réel)

### Fonctionnel / produit
- [ ] Notifications (email ou in-app) quand le SAV répond ou qu'un ticket est transféré
- [ ] Recherche full-text dans l'historique des conversations
- [ ] Export des dashboards analytics en PDF/CSV
- [ ] Rôles/permissions plus fins (ex : superviseur SAV) si le besoin se confirme
- [ ] Amélioration du pipeline RAG : reranking des chunks, ajustement automatique du seuil de qualité selon le feedback utilisateur
