# Audit B1 — SmartTicket

**Projet :** SmartTicket — Gestionnaire de tickets RAG (Mistral AI + pgvector + FastAPI)
**Date :** 2026-05-16
**Bloc :** B1 — Réaliser la collecte, le stockage et la mise à disposition des données d'un projet en intelligence artificielle

---

## 1. Tableau récapitulatif

| Critère | Intitulé | État | Résumé |
|---------|----------|------|--------|
| C1 | Extraction de données depuis sources multiples | ✅ Présent | Scraping web + ingestion PDF/DOCX/TXT via API |
| C2 | Requêtes SQL d'extraction | ⚠️ Partiel | ORM complexe + SQL natif pour migrations/pgvector ; absence d'Alembic |
| C3 | Agrégation et nettoyage | ✅ Présent | Chunking `RecursiveCharacterTextSplitter` + normalisation multi-niveaux |
| C4 | Base de données avec respect du RGPD | ✅ Présent | PostgreSQL + pgvector + soft-delete + purge auto 30 j + export RGPD |
| C5 | API REST de mise à disposition | ✅ Présent | 25 endpoints FastAPI + Swagger `/docs` + JWT + RBAC 3 rôles |

---

## 2. Détail par critère

### C1 — Extraction de données depuis sources multiples ✅

#### Sources couvertes

| Source | Module | Fichier | Lignes clés |
|--------|--------|---------|-------------|
| Web (URL unique ou sitemap) | `WebBaseLoader` (LangChain) | `backend/ingest_postgres.py` | 233–261 |
| Sitemap XML | `requests` + `xml.etree` | `backend/ingest_postgres.py` | 182–230 |
| Fichier PDF | `pypdf.PdfReader` | `backend/ingest_postgres.py` | 376–382 |
| Fichier DOCX | `python-docx` | `backend/ingest_postgres.py` | 373–375 |
| Fichier TXT | `bytes.decode` | `backend/ingest_postgres.py` | 369–372 |

#### Points notables

- **robots.txt** : respecté avant tout scraping (`_get_robots_parser` + `can_fetch`) — `ingest_postgres.py:142–178`
- **Filtrage d'extensions** : non-HTML ignorés (PDF, images, JS…) — `ingest_postgres.py:80–82`
- **Fréquence d'exécution** : déclenchement manuel via endpoint API (`POST /v1/knowledge-base/ingest-url` et `POST /v1/knowledge-base/ingest-file`), exécution en arrière-plan (`BackgroundTasks`) — `routers/knowledge.py:17–109`
- **Versionné Git** : oui (monorepo GitHub)
- **Librairies** : `requests`, `langchain-community`, `langchain-text-splitters`, `pypdf`, `python-docx`

#### Ce qui est présent / ce qui manque

| Item | État |
|------|------|
| Scraping web multi-URLs via sitemap | ✅ `ingest_postgres.py:280–304` |
| Ingestion PDF | ✅ `ingest_postgres.py:376–382` |
| Ingestion DOCX | ✅ `ingest_postgres.py:373–375` |
| Ingestion TXT | ✅ `ingest_postgres.py:369–372` |
| Respect robots.txt | ✅ `ingest_postgres.py:268–294` |
| Scheduler automatique | ❌ Absent — ingestion uniquement à la demande |

---

### C2 — Requêtes SQL d'extraction ⚠️

#### Requêtes SQL natives

| Requête | Fichier | Ligne | Usage |
|---------|---------|-------|-------|
| `CREATE EXTENSION IF NOT EXISTS vector` | `backend/main.py` | 98 | Activation pgvector au démarrage |
| `ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS feedback INTEGER` | `backend/main.py` | 113 | Migration incrémentale au startup |
| `ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS transfer_reason VARCHAR(50)` | `backend/main.py` | 114 | Migration incrémentale au startup |
| `ALTER TABLE utilisateur ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ` | `backend/main.py` | 115 | Migration RGPD au startup |
| `ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ` | `backend/main.py` | 116 | Migration RGPD au startup |
| `CREATE INDEX ON knowledge_base USING hnsw (embedding vector_cosine_ops)` | `backend/db/init-db.sql` | 98 | Index HNSW pour recherche vectorielle |
| `INSERT INTO roles ... ON CONFLICT DO NOTHING` | `backend/db/init-db.sql` | 21 | Seed des rôles initiaux |

#### Requêtes ORM complexes

| Description | Fichier | Ligne |
|-------------|---------|-------|
| Recherche vectorielle cosinus `order_by(embedding.cosine_distance(...))` | `routers/ai.py` | 65 |
| Comptage sessions avec sous-requête `sav` | `routers/analytics.py` | 64–65 |
| Agrégation quotidienne avec `date_trunc` + `group_by` | `routers/analytics.py` | 68–70 |
| Agrégation messages avec feedback par jour | `routers/analytics.py` | 82–84 |
| Tendance latence IA avec `avg` + `group_by` jour | `routers/analytics.py` | 147–156 |
| Liste sources KB avec `count` + `min(date)` groupés | `routers/knowledge.py` | 62–69 |
| Sessions transférées avec JOIN `Utilisateur` | `routers/sessions.py` | 173–177 |

#### Ce qui manque

| Item | État |
|------|------|
| Requêtes SQL natives d'extraction complexes | ⚠️ Essentiellement ORM — SQL natif limité aux migrations |
| Outil de migration Alembic | ❌ Absent — migrations exécutées via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` dans `main.py:startup` |
| Index explicites sur colonnes FK | ⚠️ Seul l'index HNSW sur `knowledge_base.embedding` est défini ; pas d'index sur `id_utilisateur`, `id_session` |

---

### C3 — Agrégation et nettoyage ✅

#### Pipeline de chunking

| Paramètre | Valeur | Fichier | Ligne |
|-----------|--------|---------|-------|
| Lib | `RecursiveCharacterTextSplitter` (LangChain) | `ingest_postgres.py` | 310, 391 |
| `chunk_size` | 1 000 caractères | `ingest_postgres.py` | 310 |
| `chunk_overlap` | 100 caractères | `ingest_postgres.py` | 310 |
| `chunk_size` (transcripts sessions) | configurable `TRANSCRIPT_CHUNK_SIZE` (défaut 1 000) | `dependencies.py` | 27 |
| `chunk_overlap` (transcripts) | `TRANSCRIPT_CHUNK_OVERLAP` (défaut 150) | `dependencies.py` | 28 |
| `MAX_KB_CHUNKS` | 80 (limite de chunks par ingestion) | `ingest_postgres.py` | 24, 322–323 |

#### Règles de normalisation

| Règle | Description | Fichier | Ligne |
|-------|-------------|---------|-------|
| Suppression `\x00` | Null bytes (incompatibles PostgreSQL) | `ingest_postgres.py` | 51 |
| Suppression caractères de contrôle | `\x01–\x08`, `\x0B`, `\x0C`, `\x0E–\x1F`, `\x7F` | `ingest_postgres.py` | 52 |
| Normalisation espaces | `re.sub(r"\s+", " ", ...)` | `ingest_postgres.py` | 53 |
| Détection contenu binaire / corrompu | ratio de caractères indéchiffrables `> 0.2` | `ingest_postgres.py` | 57–77 |
| Détection signature binaire | patterns EXIF, JFIF, ICC_PROFILE, Adobe… | `ingest_postgres.py` | 40–47, 74 |
| Détection longue chaîne base64 | token > 120 chars alphanumériques consécutifs | `ingest_postgres.py` | 73 |
| Longueur minimale | `MIN_TEXT_LENGTH = 80` chars | `ingest_postgres.py` | 38, 318–319 |
| HTML stripping | via `WebBaseLoader` (BeautifulSoup interne) | `ingest_postgres.py` | 244 |
| Sanitization texte SAV/transcripts | `sanitize_text` — supprime `\x00` | `dependencies.py` | 46–48 |

#### Dédoublonnage

| Item | État |
|------|------|
| Dédoublonnage d'URLs dans le sitemap | ✅ `dict.fromkeys(page_urls)` — `ingest_postgres.py:229` |
| Dédoublonnage de chunks par hash de contenu | ❌ Absent — re-ingestion possible d'un même document |

---

### C4 — Base de données avec respect du RGPD ✅

#### Schéma des tables

| Table | Colonnes principales | PK | FK | Contraintes notables |
|-------|---------------------|----|----|----------------------|
| `roles` | `id`, `nom_role` | `id` | — | `nom_role UNIQUE NOT NULL` |
| `utilisateur` | `id`, `username`, `email`, `password_hash`, `prenom`, `nom`, `id_role`, `date_creation`, `deleted_at` | `id` | `id_role → roles.id` | `username UNIQUE`, `email UNIQUE` |
| `chat_sessions` | `id`, `id_utilisateur`, `title`, `status`, `transfer_reason`, `date_creation`, `deleted_at` | `id` | `id_utilisateur → utilisateur.id CASCADE` | `status NOT NULL DEFAULT 'open'` |
| `chat_messages` | `id`, `id_session`, `type_envoyeur`, `contenu`, `feedback`, `date_creation` | `id` | `id_session → chat_sessions.id CASCADE` | `type_envoyeur CHECK IN ('user','ai','sav')` |
| `ai_call_logs` | `id`, `id_session`, `call_type`, `model_name`, `latency_ms`, `rag_chunks_found`, `rag_context_chars`, `success`, `error_type`, `date_creation` | `id` | `id_session → chat_sessions.id SET NULL` | `success NOT NULL DEFAULT TRUE` |
| `knowledge_base` | `id`, `source_message_id`, `contenu`, `embedding`, `category`, `source`, `date_creation` | `id` | `source_message_id → chat_messages.id SET NULL` | `embedding vector(1024) NOT NULL` |

Sources : `backend/models.py:7–74` et `backend/db/init-db.sql`

#### Extension pgvector

| Item | Preuve |
|------|--------|
| Extension activée | `db/init-db.sql:6` — `CREATE EXTENSION IF NOT EXISTS vector` |
| Activation au startup | `main.py:96–101` — `CREATE EXTENSION IF NOT EXISTS vector` |
| Type vectoriel | `Vector(1024)` sur `knowledge_base.embedding` — `models.py:71` |
| Index HNSW cosinus | `db/init-db.sql:98` — `CREATE INDEX ON knowledge_base USING hnsw (embedding vector_cosine_ops)` |
| Requête ANN | `routers/ai.py:65` — `.order_by(KnowledgeBase.embedding.cosine_distance(query_embedding))` |

#### Mesures RGPD

| Mesure | État | Fichier | Ligne |
|--------|------|---------|-------|
| Mot de passe hashé bcrypt (jamais en clair) | ✅ | `dependencies.py:13`, `routers/auth.py:63` | |
| Soft-delete `utilisateur` | ✅ `deleted_at TIMESTAMPTZ` | `models.py:25` | |
| Soft-delete `chat_sessions` | ✅ `deleted_at TIMESTAMPTZ` | `models.py:36` | |
| Purge automatique après 30 jours | ✅ APScheduler, cron `03:00 UTC` | `main.py:169–179` | |
| Purge au démarrage (enregistrements déjà expirés) | ✅ | `main.py:178` | |
| Export données personnelles (Art. 15 & 20) | ✅ `GET /v1/me/export` | `routers/auth.py:133–176` | |
| Modification profil | ✅ `PUT /v1/me` | `routers/auth.py:105–130` | |
| Changement mot de passe | ✅ `PUT /v1/me/password` | `routers/auth.py:179–190` | |
| Suppression compte par admin | ✅ soft-delete cascade sessions | `routers/users.py:89–105` | |
| `password_hash` absent des réponses API | ✅ Schémas Pydantic sans ce champ | `schemas.py:19–29` | |
| Checkbox RGPD côté frontend | ✅ | `frontend/app/(auth)/sign-up/page.tsx:206–218` | |

#### Ce qui manque

| Item | État |
|------|------|
| Alembic (migrations versionées) | ❌ Absent — migrations via `ALTER TABLE IF NOT EXISTS` au startup |
| Registre des traitements formalisé | ❌ Absent (document RGPD externe non fourni) |
| Pseudonymisation des logs IA | ⚠️ `ai_call_logs` contient `id_session` (indirectement identifiant) |

---

### C5 — API REST de mise à disposition ✅

#### Endpoints exposés

| Méthode | Chemin | Rôle requis | Description |
|---------|--------|-------------|-------------|
| `GET` | `/` | — | Health check |
| `POST` | `/v1/register` | — | Création de compte |
| `POST` | `/v1/login` | — | Connexion, retourne JWT + cookie `auth_token` |
| `POST` | `/v1/logout` | authentifié | Supprime le cookie |
| `GET` | `/v1/me` | authentifié | Profil de l'utilisateur connecté |
| `PUT` | `/v1/me` | authentifié | Mise à jour profil |
| `PUT` | `/v1/me/password` | authentifié | Changement mot de passe |
| `GET` | `/v1/me/export` | authentifié | Export RGPD (Art. 15 & 20) |
| `POST` | `/v1/setup-admin` | — | Création/promotion compte admin |
| `GET` | `/v1/users` | admin / sav | Liste des utilisateurs |
| `PUT` | `/v1/users/{id}` | admin | Modification utilisateur |
| `PUT` | `/v1/users/{id}/role` | admin | Changement de rôle |
| `DELETE` | `/v1/users/{id}` | admin | Soft-delete utilisateur |
| `POST` | `/v1/sessions` | authentifié | Créer une session de chat |
| `GET` | `/v1/sessions` | authentifié | Lister ses sessions |
| `DELETE` | `/v1/sessions/{id}` | authentifié | Supprimer une session (soft) |
| `POST` | `/v1/sessions/{id}/close` | authentifié | Clôturer + résumé IA + indexation transcript |
| `POST` | `/v1/sessions/{id}/transfer` | authentifié | Transférer vers agent humain |
| `POST` | `/v1/sessions/{id}/resolve` | admin / sav | Rétablir l'IA après transfert |
| `GET` | `/v1/sessions/transferred` | admin / sav | Sessions en attente d'un agent |
| `GET` | `/v1/messages` | authentifié | Lister les messages d'une session |
| `POST` | `/v1/messages` | authentifié | Créer un message |
| `PATCH` | `/v1/messages/{id}/feedback` | authentifié | Feedback pouce haut/bas |
| `POST` | `/v1/ask/stream` | authentifié | Interroger Mistral AI avec RAG (streaming) |
| `POST` | `/v1/knowledge-base/ingest-url` | admin / sav | Indexer une URL / sitemap |
| `GET` | `/v1/knowledge-base/ingest-status` | authentifié | Statut d'un job d'indexation |
| `GET` | `/v1/knowledge-base/robots-check` | authentifié | Analyser robots.txt d'un domaine |
| `GET` | `/v1/knowledge-base/sources` | authentifié | Lister les sources indexées |
| `DELETE` | `/v1/knowledge-base/sources` | admin / sav | Supprimer une source |
| `POST` | `/v1/knowledge-base/ingest-file` | admin / sav | Indexer un PDF / DOCX / TXT |
| `GET` | `/v1/analytics/stats` | admin / sav | Statistiques service IA |
| `GET` | `/v1/analytics/ai-metrics` | admin / sav | Métriques monitoring IA |

#### Authentification et sécurité

| Mesure | État | Fichier | Ligne |
|--------|------|---------|-------|
| JWT HS256 | ✅ | `dependencies.py:66–70` | |
| Cookie `auth_token` HttpOnly + SameSite=strict | ✅ | `routers/auth.py:82–83` | |
| Double auth (Bearer token OU cookie) | ✅ | `dependencies.py:73–88` | |
| RBAC 3 rôles (user / sav / admin) | ✅ | `dependencies.py:98–101` | |
| `SECRET_KEY` obligatoire au démarrage | ✅ | `main.py:23–24` | |
| CORS restreint aux origines configurées | ✅ | `main.py:43–58` | |
| Swagger / OpenAPI à `/docs` | ✅ | FastAPI auto-généré | |
| Mot de passe absent des réponses | ✅ | `schemas.py:19–29` | |
| Validation Pydantic des entrées | ✅ | `schemas.py` | |
| `COOKIE_SECURE` en production | ✅ | `routers/auth.py:81` | |

#### OWASP Top 10 — mesures appliquées

| Risque OWASP | Mesure en place |
|--------------|-----------------|
| A01 — Contrôle d'accès brisé | RBAC + ownership check sur sessions/messages |
| A02 — Défaillances cryptographiques | bcrypt pour les mots de passe, JWT signé HS256 |
| A03 — Injection | Requêtes ORM paramétrées (SQLAlchemy), validation Pydantic |
| A07 — Défaillances d'authentification | Cookie HttpOnly + SameSite, expiration JWT |
| A09 — Journalisation insuffisante | `ai_call_logs` + `logging` structuré dans `main.py` |

---

## 3. Synthèse des points d'amélioration

| Priorité | Item | Impact |
|----------|------|--------|
| Haute | Mettre en place Alembic pour les migrations | C2, C4 : traçabilité des évolutions de schéma |
| Moyenne | Ajouter des index sur `id_utilisateur` et `id_session` | C2 : performance des requêtes |
| Moyenne | Ajouter un hash de déduplication sur `knowledge_base` | C3 : éviter la réingestion de documents identiques |
| Faible | Anonymiser `id_session` dans `ai_call_logs` | C4 : RGPD — pseudonymisation des logs |
| Faible | Ajouter un scheduler d'ingestion automatique | C1 : fraîcheur des données |
