# Journal des décisions techniques — Pipeline RAG

Le modèle Mistral étant une API tierce figée (pas de fine-tuning possible dans le cadre de ce projet), l'amélioration itérative du système IA porte sur les composants sous contrôle direct : base de connaissances, paramètres de chunking, top-K de la recherche vectorielle, prompt template, filtres de qualité.

Ce document trace les décisions techniques prises au cours du projet, déclenchées par les signaux du monitoring ou par des observations empiriques lors du développement.

---

## Format d'une décision

```
### [Date] — [Titre court]

**Signal observé** : ...
**Hypothèse** : ...
**Action prise** : ...
**Mesure d'impact** : ...
**Statut** : Adopté / Rejeté / En test
```

---

## Décisions prises

### 2026-05-13 — Taille de chunk à 1 000 caractères avec overlap 100

**Signal observé** : lors des premiers tests avec des chunks de 500 caractères, le pipeline RAG retournait fréquemment des fragments sans contexte suffisant — phrases coupées en milieu de développement, références orphelines (« comme mentionné ci-dessus »). Les réponses générées manquaient de cohérence.

**Hypothèse** : un chunk trop court fragmente le contexte sémantique et produit des embeddings instables. Un chunk trop long (> 2 000 caractères) dilue le signal de similarité cosinus et peut dépasser la fenêtre d'embedding optimale du modèle `mistral-embed`.

**Action prise** : paramétrage de `RecursiveCharacterTextSplitter` avec `chunk_size=1000` et `chunk_overlap=100` (10 % de recouvrement aux frontières). Ce splitter respecte les séparateurs naturels du texte (paragraphes, phrases) avant de couper arbitrairement.

**Mesure d'impact** : amélioration empirique de la pertinence des réponses mesurée sur ~30 questions de test couvrant les thèmes principaux de la base de connaissances. Le taux de requêtes avec `rag_chunks_found > 0` est passé de ~70 % à ~90 % sur la série de tests.

**Statut** : Adopté — `backend/ingest_postgres.py:310`

---

### 2026-05-13 — Plafond `MAX_KB_CHUNKS = 80` par ingestion

**Signal observé** : l'ingestion d'un document volumineux (guide utilisateur, FAQ complète) produisait plus de 200 chunks. L'analyse manuelle des derniers chunks montrait qu'ils contenaient majoritairement des éléments sans valeur métier : en-têtes de page, mentions légales répétées, footers de navigation, numéros de section.

**Hypothèse** : limiter le nombre de chunks par ingestion force à indexer les parties les plus denses en information (généralement en début de document) et maintient la base de connaissances dense et précise. Au-delà de 80 chunks, le rapport signal/bruit se dégrade.

**Action prise** : ajout de la constante `MAX_KB_CHUNKS = 80` configurable via variable d'environnement, appliquée après le découpage et le filtrage qualité (`backend/ingest_postgres.py:395`).

**Mesure d'impact** : amélioration de la qualité moyenne du `rag_context_chars` retourné (contextes plus concentrés, moins de répétition). Visible dans `/v1/analytics/ai-metrics` via la métrique `avg_rag_chunks`.

**Statut** : Adopté — `backend/ingest_postgres.py:24`

---

### 2026-05-13 — Filtrage du contenu binaire avant embedding

**Signal observé** : lors du scraping de pages web contenant des images inline (formats base64 data-URI, EXIF embedded, signatures JFIF), le pipeline injectait des chaînes binaires encodées dans les chunks. Ces chunks produisaient des embeddings aberrants qui remontaient dans certaines recherches vectorielles pourtant sans lien thématique avec la question posée.

**Hypothèse** : les chaînes binaires longues (> 120 caractères alphanumériques consécutifs, ratio de caractères de remplacement `�` > 2 %) génèrent des embeddings sans sémantique exploitable, qui polluent l'espace vectoriel et dégradent la précision de la recherche cosinus.

**Action prise** : ajout d'une fonction de scoring de « binarité » (`_looks_like_binary_text`) qui rejette tout segment dépassant 20 % de caractères indéchiffrables ou présentant des signatures connues (EXIF, JFIF, ICC_PROFILE, Adobe, Photoshop). Également : rejet des tokens base64 de plus de 120 caractères consécutifs. (`backend/ingest_postgres.py:57–77`)

**Mesure d'impact** : disparition des chunks « poubelle » dans la base de connaissances observable via `GET /v1/knowledge-base/sources`. Amélioration de la cohérence des résultats RAG sur les sujets contenant des pages illustrées.

**Statut** : Adopté — `backend/ingest_postgres.py:57`

---

### 2026-05-13 — Soft-delete des sessions plutôt que suppression physique immédiate

**Signal observé** : besoin RGPD de respecter un délai de rétention de 30 jours avant suppression définitive. Simultanément, besoin analytique de conserver les sessions transférées pour comprendre quels sujets le RAG ne couvre pas (raisons de transfert : technique / complexe / sensible / autre).

**Hypothèse** : une suppression physique immédiate détruirait les données d'analyse avant qu'elles aient pu être exploitées. Un soft-delete permet de concilier conformité RGPD (purge garantie à 30 jours) et analytics (analyse des sessions transférées).

**Action prise** : ajout de colonnes `deleted_at TIMESTAMPTZ` sur `utilisateur` et `chat_sessions`. Toutes les requêtes filtrent sur `deleted_at IS NULL`. Job APScheduler de purge quotidienne à 3 h UTC (`main.py:169`). Purge immédiate au démarrage pour traiter les enregistrements déjà expirés.

**Mesure d'impact** : le dashboard analytics (`/v1/analytics/stats`) peut calculer les raisons de transfert sur les 30 derniers jours, ce qui permet d'identifier les lacunes de la base de connaissances et d'orienter les prochaines ingestions.

**Statut** : Adopté — `backend/models.py:25, 36` / `backend/main.py:65`

---

### 2026-05-14 — Ajout du monitoring IA avec journalisation des appels

**Signal observé** : impossibilité de mesurer la qualité du RAG dans le temps. Sans historique des appels, il était impossible de détecter une dégradation de la base de connaissances (après une mauvaise ingestion par exemple) ou de comparer les performances entre deux périodes.

**Hypothèse** : tracer chaque appel au modèle (latence, chunks RAG trouvés, succès/erreur) permet de construire des métriques de qualité objectives et d'activer la boucle d'amélioration itérative.

**Action prise** : ajout de la table `ai_call_logs` et insertion systématique dans le handler de streaming (`backend/routers/ai.py:103–115`). Développement de deux endpoints analytics : `/v1/analytics/stats` (taux de résolution, satisfaction) et `/v1/analytics/ai-metrics` (latence, erreur, RAG quality, KB Health Score).

**Mesure d'impact** : le KB Health Score (0–100) donne une vision synthétique de l'état de la base de connaissances. Les alertes calculées (seuils warning/critical) permettent de détecter proactivement les dégradations sans surveillance manuelle permanente.

**Statut** : Adopté — `backend/routers/analytics.py` / `backend/routers/ai.py:103`

---

### 2026-05-14 — Respect du robots.txt avant tout scraping

**Signal observé** : lors des premiers tests d'ingestion sur des sites tiers, certaines URL généraient des erreurs 403 ou des réponses HTML vides (pages de login, anti-scraping). Par ailleurs, le scraping de pages interdites par le propriétaire du site constitue un risque légal.

**Hypothèse** : respecter le fichier `robots.txt` du domaine cible élimine les URL protégées, réduit les erreurs d'ingestion et sécurise juridiquement la collecte de données.

**Action prise** : lecture du `robots.txt` avant toute ingestion via `urllib.robotparser.RobotFileParser`. Filtrage des URL interdites dans le pipeline de scraping. Endpoint `/v1/knowledge-base/robots-check` permettant de pré-visualiser le nombre d'URL autorisées/bloquées avant de lancer une ingestion. (`backend/ingest_postgres.py:142, 268–294`)

**Mesure d'impact** : réduction significative des erreurs d'ingestion. Ingestion plus propre et plus rapide (moins de tentatives sur des URL interdites). La pré-visualisation permet à l'admin de décider en connaissance de cause.

**Statut** : Adopté — `backend/ingest_postgres.py:80, 142`

---

### 2026-07-07 — Reranking hybride + quarantaine des chunks à feedback négatif

**Signal observé** : le retrieval ne s'appuyait que sur la distance cosinus brute (top-K pgvector direct). Aucun signal ne permettait de corriger un chunk sémantiquement proche de la question mais qui avait déjà généré des réponses mal notées par les utilisateurs (`chat_messages.feedback`) — le pipeline n'apprenait jamais de ce feedback après l'ingestion.

**Hypothèse** : combiner le rang de similarité vectorielle avec (1) un recouvrement lexical simple entre la question et le contenu du chunk, et (2) le feedback net accumulé sur ce chunk, permet d'affiner le classement sans dépendre d'un modèle de reranking supplémentaire coûteux (cross-encoder). Un chunk au feedback très négatif doit être exclu (quarantaine), quelle que soit sa similarité — c'est exactement la piste « Quarantaine des chunks à feedback négatif répété » listée ci-dessous.

**Action prise** : nouvelle colonne `chat_messages.source_kb_ids INTEGER[]` traçant les chunks utilisés pour générer chaque réponse IA. Nouveau module `backend/rag_reranking.py` (`rerank_chunks`) : sur-échantillonnage du retrieval pgvector (`KB_TOP_K * RERANK_FETCH_MULTIPLIER`, défaut ×3), puis reclassement par score composite `similarité (rang) + 0.3 × recouvrement lexical + 0.2 × feedback normalisé`, avec exclusion des chunks dont le feedback net ≤ `RERANK_QUARANTINE_THRESHOLD` (défaut -3, seuil configurable). Câblé dans `backend/routers/ai.py::ask_question_stream`.

**Mesure d'impact** : `rag_chunks_found` (déjà suivi dans `ai_call_logs`) peut désormais être inférieur à `KB_TOP_K` même quand des candidats existent, signe visible que le filtrage qualité opère. Pas encore de mesure en production (fonctionnalité tout juste livrée) — à suivre via `avg_rag_chunks` et `no_context_rate` sur `/v1/analytics/ai-metrics` dans les semaines suivant le déploiement.

**Statut** : Adopté — `backend/rag_reranking.py` / `backend/routers/ai.py`

---

## Pistes identifiées pour V2 (non implémentées)

Ces décisions sont **identifiées comme pertinentes** mais reportées faute de signal suffisant pour justifier leur priorité dans le périmètre actuel :

| Piste | Signal qui déclencherait l'implémentation | Impact attendu |
|-------|------------------------------------------|----------------|
| **Dédoublonnage par hash de contenu** sur `knowledge_base` | Taux de doublons > 5 % détecté via requête SQL sur `contenu` | Éviter la réingestion d'un même document, maintenir une base propre |
| **Alertes actives** (notification push) | Dashboard consulté < 1 fois par semaine par l'admin | Les alertes calculées dans le dashboard deviennent des notifications proactives |
| **Index sur clés étrangères** (`id_utilisateur`, `id_session`) | Latence des requêtes JOIN > 100 ms en production | Amélioration des performances sur les jointures fréquentes |
| **Évaluation automatique de la génération** (benchmark Q/R) | Base de connaissances > 500 chunks | Mesurer la qualité de génération de façon reproductible, indépendamment du feedback utilisateur |

---

## Métriques de référence

Les décisions ci-dessus sont déclenchées par les métriques suivantes, accessibles dans le dashboard `/monitoring` et via `/v1/analytics/ai-metrics` :

| Métrique | Source | Seuil warning | Seuil critical |
|----------|--------|---------------|----------------|
| Latence moyenne IA | `ai_call_logs.latency_ms` (avg) | > 5 000 ms | > 10 000 ms |
| Taux d'erreur IA | `ai_call_logs.success = false` | > 5 % | > 15 % |
| Taux `no_context` | `rag_chunks_found = 0` | > 70 % | — |
| Taux de résolution IA | sessions non transférées | < 70 % | < 50 % |
| Score satisfaction | `chat_messages.feedback` (ratio positif) | < 3/5 | < 2/5 |
| KB Health Score | formule pondérée (70 % context quality + 30 % reliability) | — | — |

*Sources : `backend/routers/analytics.py:15–21` et `backend/routers/analytics.py:224–234`*
