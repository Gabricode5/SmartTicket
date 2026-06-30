# Rapport de soutenance
## SmartTicket — Gestionnaire de tickets intelligent avec assistant IA
### Titre RNCP Concepteur Développeur en Intelligence Artificielle (Niveau 6)
### Compétences C14 à C19

---

**Candidat :** Gabriel Guery  
**Date de soutenance :** À compléter  
**Dépôt :** https://github.com/guerygabriel/SmartTicket  
**Tag de production :** v1.0.0 (2026-05-18)

---

## 1. Présentation du projet et du commanditaire

### Contexte et besoin

SmartTicket est un système de gestion de tickets de support enrichi d'un assistant conversationnel basé sur l'intelligence artificielle. Le besoin de départ est celui de toute organisation proposant un service client : réduire le volume d'interventions humaines sur les demandes répétitives et à faible valeur ajoutée, tout en maintenant une qualité de réponse élevée. Le commanditaire — fictif dans le cadre de ce titre, mais ancré dans un cas d'usage réel — est une PME souhaitant automatiser son premier niveau de support sans abandonner la possibilité d'une escalade vers un opérateur humain.

Le périmètre fonctionnel couvre trois profils d'utilisateurs distincts : le **client** qui pose ses questions via une interface de chat, l'**opérateur SAV** qui prend en charge les cas que l'IA ne peut pas résoudre, et l'**administrateur** qui pilote la base de connaissances et les métriques de performance. Cette segmentation a guidé l'ensemble des choix de conception, depuis le modèle de données jusqu'à l'architecture de déploiement.

### Stack technique retenue

L'application repose sur quatre couches principales. Le **backend** est développé en Python 3.11 avec le framework FastAPI, qui expose 25 endpoints REST organisés en 7 routeurs sous le préfixe `/v1`. Le **frontend** est une application Next.js 16 (App Router) en TypeScript, qui fait office de Backend-for-Frontend : elle proxifie les appels API vers le backend et gère le rendu côté serveur. La **base de données** est PostgreSQL 16 avec l'extension `pgvector`, qui stocke à la fois les données relationnelles (utilisateurs, sessions, messages) et les embeddings vectoriels (1 024 dimensions) pour la recherche sémantique. Le **service d'intelligence artificielle** est fourni par l'API Mistral, avec deux modèles : `mistral-embed` pour la vectorisation des documents et des questions, et `mistral-small-latest` pour la génération des réponses en mode streaming.

[CAPTURE : diagramme C4 container depuis `docs/E4/C15/02_diagramme_flux_donnees.md` — montrant les quatre blocs (Next.js / FastAPI / PostgreSQL+pgvector / Mistral API) et leurs flux]

L'ensemble est containerisé via Docker et déployé automatiquement sur Render.com, décrit de manière déclarative dans `render.yaml`. Le cycle de vie du code est géré par une pipeline GitHub Actions (`ci.yml`) composée de trois jobs : tests backend, tests frontend, et déploiement conditionnel.

---

## 2. C14 — Analyser le besoin et rédiger les spécifications fonctionnelles

> **Libellé officiel :** Analyser le besoin d'application d'un commanditaire intégrant un service d'intelligence artificielle, en rédigeant les spécifications fonctionnelles et en le modélisant, dans le respect des standards d'utilisabilité et d'accessibilité, afin d'établir avec précision les objectifs de développement correspondant au besoin et à la faisabilité technique.

### Analyse du besoin et rédaction des spécifications

L'analyse du besoin a produit un document de spécifications fonctionnelles structuré en huit user stories, consultable dans `docs/E4/C14/01_specifications_fonctionnelles.md`. Chaque user story suit le format *En tant que / Je veux / Afin de*, complété par un bloc de contexte, trois scénarios (nominal, alternatif, échec) et un ensemble de critères d'acceptation couvrant les dimensions fonctionnelle, performance, sécurité et accessibilité.

Les huit user stories couvrent l'ensemble du périmètre applicatif :

- **US-01** : poser une question en langage naturel (profil client)
- **US-02** : recevoir une réponse augmentée par la base documentaire via RAG (profil client)
- **US-03** : escalader vers un opérateur humain avec sélection du motif (profil client)
- **US-04** : suivre l'état de ses tickets (profil client)
- **US-05** : reprendre une conversation transférée (profil SAV)
- **US-06** : évaluer la qualité d'une réponse du bot par feedback (profil SAV)
- **US-07** : gérer la base documentaire — ajouter, modifier, supprimer des sources (profil admin)
- **US-08** : consulter le tableau de bord des métriques (profil admin)

Ce découpage en trois profils distincts a directement guidé la conception du RBAC (système de contrôle d'accès par rôle), documenté en C15 et implémenté en C17.

[CAPTURE : tableau récapitulatif des 8 user stories depuis `docs/E4/C14/01_specifications_fonctionnelles.md` — colonnes Profil / Action / Bénéfice / Critères clés]

### Modélisation

La modélisation des données a suivi la méthode Merise, documentée dans `docs/E4/C14/02_modelisation_donnees.md`. J'ai procédé dans l'ordre MCD → MLD → MPD, avant de traduire le MPD en DDL SQL dans `backend/db/init-db.sql`. Le schéma final compte six tables :

- `roles` — référentiel des rôles applicatifs (`user`, `sav`, `admin`)
- `utilisateur` — comptes avec hachage de mot de passe et colonne `deleted_at` pour la conformité RGPD
- `chat_sessions` — sessions avec statut (`open` / `transferred` / `resolved` / `closed`), motif de transfert catégorisé, et colonne `deleted_at`
- `chat_messages` — messages avec discriminant `type_envoyeur` (`user` / `ai` / `sav`) et colonne `feedback` (-1 / 1 / NULL)
- `ai_call_logs` — journal de monitoring de chaque appel au modèle (latence, chunks RAG trouvés, succès/erreur, modèle utilisé)
- `knowledge_base` — chunks de la base documentaire avec colonne `embedding vector(1024)` et index HNSW cosinus

La contrainte IA est directement intégrée dans le schéma relationnel : la colonne `embedding vector(1024)` de la table `knowledge_base` (`init-db.sql`, ligne 91) est la pièce centrale du pipeline RAG. L'index HNSW est défini ligne 98 : `CREATE INDEX ON knowledge_base USING hnsw (embedding vector_cosine_ops)`. Ce choix de stocker les vecteurs dans PostgreSQL (via `pgvector`) plutôt que dans une base vectorielle dédiée (ChromaDB, Pinecone) est une décision architecturale justifiée en C15.

Les parcours utilisateurs sont documentés dans `docs/E4/C14/03_parcours_utilisateurs.md` sous forme de diagrammes de flux séquentiels couvrant les trois profils.

[CAPTURE : diagramme MCD Merise depuis `docs/E4/C14/02_modelisation_donnees.md` ou `docs/schema_bdd.drawio`]

### Faisabilité technique de l'intégration IA

L'étude de faisabilité est documentée dans `docs/E4/C15/04_poc_preproduction.md`. J'y ai évalué deux alternatives pour le service IA : **Ollama en self-hosted** (modèle tournant localement, présent dans `docker-compose.yml` pour l'environnement de développement) versus **l'API Mistral** (service externe). La comparaison a porté sur trois axes : la qualité des embeddings (1 024 dimensions pour `mistral-embed` versus 768 pour les modèles Ollama testés), la latence de génération (insuffisante sans GPU dédié en self-hosted), et les contraintes RGPD (les données de conversation sont transmises à l'API Mistral, ce qui nécessite une justification dans le cadre du RGPD). Le PoC a conclu en faveur de l'API Mistral pour la production, avec Ollama maintenu en développement local pour tester sans coût API.

### Accessibilité WCAG 2.1 AA

L'accessibilité n'est pas traitée comme une couche d'habillage ajoutée après coup : chaque user story intègre des critères d'acceptation WCAG 2.1 AA explicites. Par exemple, US-01 exige que le champ de saisie expose `role="textbox"` et `aria-label="Votre message"` (critère 4.1.2), que l'envoi soit réalisable uniquement au clavier (critère 2.1.1), et que les messages d'erreur de validation soient liés au champ via `aria-describedby` (critère 3.3.1). US-02 exige que l'indicateur de chargement soit annoncé aux lecteurs d'écran via `aria-live="polite"` (critère 4.1.3). US-04 interdit d'utiliser uniquement la couleur pour distinguer les statuts de ticket (critère 1.4.1).

La conformité WCAG 2.1 AA est synthétisée dans la matrice disponible dans `docs/E4/C14/04_accessibilite.md`, qui croise 13 critères avec les 8 user stories. Cette traçabilité garantit que les exigences d'accessibilité ont été pensées dès la phase d'analyse et pas ajoutées rétrospectivement.

[CAPTURE : matrice WCAG 2.1 AA depuis `docs/E4/C14/04_accessibilite.md` — 13 critères × 8 US]

### Points faibles à renforcer

L'accessibilité est bien documentée dans les spécifications mais son implémentation réelle côté frontend est difficile à vérifier statiquement depuis le code seul : il n'existe pas de tests automatisés d'accessibilité (axe-core, lighthouse CI) dans le pipeline. Les critères WCAG présents dans les user stories constituent des engagements, pas des preuves d'implémentation. Ce point devra être adressé pour une V2 rigoureuse.

---

## 3. C15 — Concevoir le cadre technique

> **Libellé officiel :** Concevoir le cadre technique d'une application intégrant un service d'intelligence artificielle, à partir de l'analyse du besoin, en spécifiant l'architecture technique et applicative et en préconisant les outils et méthodes de développement, pour permettre le développement du projet.

### Architecture technique et applicative

L'architecture retenue est un **monolithe modulaire Backend-for-Frontend (BFF)**. Le frontend Next.js n'est pas une simple interface graphique : il joue un rôle actif en servant de BFF, proxifiant les appels API et masquant le backend aux clients externes. Cette décision est documentée dans `docs/E4/C15/01_specifications_techniques.md` et se matérialise concrètement dans `frontend/next.config.ts`, où les rewrites proxifient `/api/*` vers le backend sur la variable d'environnement `NEXT_PUBLIC_API_URL`.

J'ai écarté une architecture microservices pour deux raisons principales. D'abord, la complexité opérationnelle (service mesh, discovery, latences inter-services) n'est pas justifiée pour une équipe de développement solo. Ensuite, la contrainte IA de streaming SSE (Server-Sent Events) est plus simple à gérer lorsque le proxy BFF et le producteur de stream sont dans des contextes réseau cohérents. La route `/api/ask` du frontend proxifie vers `POST /v1/ask/stream` du backend, gérant le chunked transfer encoding du stream sans rupture.

### Spécification de l'architecture IA : le pipeline RAG

La décision architecturale la plus critique est le choix de **pgvector comme base vectorielle plutôt que ChromaDB**. L'alternative ChromaDB figurait dans les dépendances initiales (`chromadb` est présent dans `backend/requirements.txt` mais jamais importé dans le code de production) : elle a été remplacée par pgvector après analyse. Les raisons sont documentées dans `docs/E3/RAG_DECISIONS_LOG.md` et `docs/E4/C15/01_specifications_techniques.md` : un stockage unifié dans PostgreSQL évite de maintenir deux systèmes de persistance (un relationnel, un vectoriel), garantit les propriétés ACID sur les opérations combinées (ex : soft-delete d'un utilisateur et de ses chunks associés), et simplifie le backup en production (un seul service PostgreSQL managé sur Render).

Le pipeline RAG est spécifié comme suit dans les documents d'architecture, puis implémenté dans `backend/ingest_postgres.py` et `backend/routers/ai.py` :

1. **Ingestion** : l'administrateur soumet une URL, un fichier PDF, DOCX ou TXT via l'endpoint `POST /v1/knowledge-base/ingest-url` ou `POST /v1/knowledge-base/ingest-file`. Le contenu est découpé en chunks de 1 000 caractères avec un overlap de 100 (`ingest_postgres.py`, ligne 310 : `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)`), chaque chunk est vectorisé par `mistral-embed` et stocké dans `knowledge_base.embedding` (colonne `vector(1024)`).

2. **Inférence** : lors d'une question, l'endpoint `POST /v1/ask/stream` vectorise la question via `embed_text()`, puis interroge pgvector avec une recherche cosinus HNSW (ligne 65 de `routers/ai.py` : `.order_by(models.KnowledgeBase.embedding.cosine_distance(query_embedding)).limit(KB_TOP_K)`). Les chunks les plus proches sont assemblés en contexte, injectés dans un prompt template défini dans `dependencies.py` (ligne 50, fonction `build_rag_prompt()`), et envoyés à `mistral-small-latest` en mode streaming.

[CAPTURE : diagramme du flux RAG depuis `docs/E4/C15/02_diagramme_flux_donnees.md` — séquence Question → Embedding → Cosine Search → Prompt → Stream]

### Inventaire technique et justification des choix d'outils

L'inventaire complet des 30+ bibliothèques avec leurs justifications est documenté dans `docs/E4/C15/00_inventaire_technique.md`. Les choix structurants sont les suivants :

**FastAPI** a été préféré à Django REST Framework pour sa performance async native (ASGI, Starlette) indispensable au streaming SSE, et pour son système de dépendances injectées (`Depends`) qui rend la déclaration du RBAC très explicite à la lecture du code. Chaque endpoint sensible déclare sa garde dans sa signature de fonction.

**Next.js 16 App Router** a été préféré à une SPA React pure pour deux raisons : le routage serveur permet de gérer l'authentification au niveau middleware (redirection vers `/login` si pas de token), et le support natif du streaming SSE côté client permet d'afficher les tokens générés par Mistral en temps réel sans bibliothèque tierce.

**LangChain** (via `langchain-community` et `langchain-text-splitters`) est utilisé uniquement pour le chargement de pages web (`WebBaseLoader`) et le découpage de texte (`RecursiveCharacterTextSplitter`). Il n'est pas utilisé comme orchestrateur de chaînes : j'ai préféré implémenter le pipeline RAG directement en Python pour garder le contrôle total sur chaque étape et éviter l'abstraction opaque que LangChain impose sur la gestion des prompts et des appels modèle.

**pnpm** est utilisé comme gestionnaire de paquets frontend (`pnpm-workspace.yaml`, `pnpm-lock.yaml`) pour ses performances d'installation et sa gestion déterministe des dépendances via le lock file.

### Eco-responsabilité

L'impact environnemental du projet est traité dans `docs/E4/C15/03_eco_responsabilite.md`. L'utilisation de l'API Mistral (infrastructure partagée, pas de GPU dédié) plutôt qu'un modèle auto-hébergé réduit l'empreinte carbone opérationnelle du projet. Le déploiement sur Render free tier minimise les ressources allouées en dehors des périodes d'activité.

### Points faibles à renforcer

L'architecture est bien spécifiée dans les documents, mais il n'existe pas de diagramme de séquence formalisé (UML ou PlantUML) dans le dépôt : les flux sont décrits en texte et dans des diagrammes Mermaid informels. Un diagramme C4 niveau 3 (composants internes du backend) serait un ajout utile pour la soutenance.

---

## 4. C16 — Coordonner la réalisation en contexte Agile et MLOps

> **Libellé officiel :** Coordonner la réalisation technique d'une application d'intelligence artificielle en s'intégrant dans une conduite agile de projet et un contexte MLOps et en facilitant les temps de collaboration dans le but d'atteindre les objectifs de production et de qualité.

### Conduite de projet et versioning

Le versioning du projet suit la convention **Keep a Changelog** avec **Semantic Versioning** (documenté ligne 5-6 du `CHANGELOG.md`). La version `1.0.0`, taguée le 2026-05-18 et référencée sur GitHub via `[1.0.0]: https://github.com/guerygabriel/SmartTicket/releases/tag/v1.0.0`, marque la livraison de l'ensemble du périmètre fonctionnel : 25 endpoints REST, pipeline RAG complet, streaming, RBAC, conformité RGPD, dashboard analytics et monitoring IA.

Le `CHANGELOG.md` documente de manière structurée l'ensemble des livrables dans sept catégories : Backend FastAPI, Base de données, Sécurité & RGPD, Ingestion de la base de connaissances, Monitoring & Analytics, Frontend Next.js, Infrastructure. Cette granularité dans le changelog reflète une démarche de livraison incrémentale même sur une branche unique.

[CAPTURE : extrait du CHANGELOG.md — section v1.0.0 avec les 7 catégories de livrables]

Le plan de projet est formalisé dans `docs/Plan_Projet.xlsx` (Gantt avec jalons et estimations de charge). L'audit de fin de sprint E3, disponible dans `docs/E3/AUDIT_E3.md`, retrace le bilan du dernier cycle : déploiement, monitoring, versioning.

### Contexte MLOps : suivi et amélioration itérative du pipeline IA

Le projet n'utilise pas MLflow ni DVC — ces outils présupposent un cycle d'entraînement de modèles que l'architecture ne comporte pas (les modèles Mistral sont consommés via API et ne sont pas entraînés). En revanche, j'ai mis en place une **boucle d'amélioration itérative** couvrant les composants du pipeline sous contrôle direct : base de connaissances, paramètres de chunking, prompt template, filtres de qualité. Cette démarche est documentée dans `docs/E3/RAG_DECISIONS_LOG.md`, qui constitue l'équivalent fonctionnel d'un journal d'expériences MLflow.

Le journal contient six décisions techniques adoptées, chacune suivant le format structuré `Signal observé → Hypothèse → Action prise → Mesure d'impact → Statut`. Deux exemples illustrent la démarche :

**ADR-01 (2026-05-13) — Chunk size à 1 000 caractères :** le signal déclencheur a été l'observation que des chunks de 500 caractères produisaient des fragments sans contexte suffisant ("phrases coupées en milieu de développement, références orphelines"). L'action prise — `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)` à `ingest_postgres.py:310` — a fait passer le taux de requêtes avec `rag_chunks_found > 0` de ~70 % à ~90 % sur une série de 30 questions de test.

**ADR-05 (2026-05-14) — Table ai_call_logs :** l'impossibilité de mesurer la qualité du RAG dans le temps a conduit à instrumenter chaque appel au modèle. Le handler de streaming (`routers/ai.py`, lignes 103-115) enregistre systématiquement dans `ai_call_logs` la latence, le nombre de chunks RAG trouvés, le type de modèle et le statut succès/erreur. Ces données alimentent deux endpoints analytics (`/v1/analytics/stats` et `/v1/analytics/ai-metrics`) et le dashboard de monitoring.

### Monitoring opérationnel de la qualité IA

La table `ai_call_logs` (`models.py`, lignes 50-62) stocke six champs de monitoring par appel : `latency_ms`, `rag_chunks_found`, `rag_context_chars`, `success`, `error_type`, `model_name`. Ces données alimentent des métriques calculées en temps réel dans `routers/analytics.py` :

- **Taux d'erreur IA** (lignes 120-125) : `failed_calls / total_calls * 100`, seuil warning > 5 %, critical > 15 %
- **Latence moyenne** (lignes 127-132) : `AVG(latency_ms)` sur les appels réussis, seuil warning > 5 000 ms, critical > 10 000 ms
- **Taux `no_context`** (lignes 140-145) : proportion d'appels avec `rag_chunks_found = 0`, seuil warning > 70 %
- **KB Health Score** (lignes 216-221) : formule pondérée `context_quality * 0.7 + reliability * 0.3`, calculé uniquement si `total_calls >= 5`
- **Comparaison périodes** (lignes 183-213) : comparaison de la latence, du taux d'erreur et du taux `no_context` entre la période courante et la période précédente de même durée

Les alertes sont générées automatiquement (lignes 223-234 de `analytics.py`) et exposées dans la réponse JSON de `/v1/analytics/ai-metrics` sous forme de liste d'objets `{level, metric, message, value, threshold}`.

[CAPTURE : dashboard `/monitoring` en production — 5 métriques avec indicateurs warning/critical et comparaison de périodes]

Le journal `RAG_DECISIONS_LOG.md` identifie également cinq pistes V2 non implémentées, dont le signal déclencheur est précisément quantifié — par exemple : "dédoublonnage par hash si le taux de doublons dépasse 5 %", ou "quarantaine des chunks à 3 feedbacks négatifs consécutifs". Cette anticipation structurée constitue une roadmap d'amélioration continue du système IA.

### Points faibles à renforcer

La conduite de projet est celle d'un développeur solo : il n'y a pas de board Kanban, pas de sprints formels, pas de PRs ni de code reviews documentées dans le dépôt (un seul commiteur direct sur `main`). Pour une présentation en contexte d'équipe, il faudrait soit simuler un flux de branches avec PRs, soit reconnaître et documenter explicitement ce choix organisationnel comme une contrainte du contexte projet individuel.

---

## 5. C17 — Développer les composants techniques et les interfaces

> **Libellé officiel :** Développer les composants techniques et les interfaces d'une application en utilisant les outils et langages de programmation adaptés et en respectant les spécifications fonctionnelles et techniques, les standards et normes d'accessibilité, de sécurité et de gestion des données en vigueur dans le but de répondre aux besoins fonctionnels identifiés.

### Composants backend : architecture des 7 routeurs

Le backend FastAPI expose 25 endpoints organisés en sept routeurs, tous préfixés `/v1` (déclaration dans `main.py`, lignes 61-62). La documentation Swagger est générée automatiquement et accessible à `/docs`. Chaque routeur porte une responsabilité métier distincte :

- **`auth.py`** — inscription, connexion (émission JWT), déconnexion, `GET/PUT /me`, changement de mot de passe, export RGPD
- **`sessions.py`** — création, liste, clôture, transfert (avec motif), résolution de sessions
- **`messages.py`** — liste, création de messages, mise à jour du feedback
- **`ai.py`** — `POST /ask/stream` : le cœur du pipeline RAG avec streaming SSE
- **`knowledge.py`** — ingestion URL/fichier, vérification robots.txt, liste et suppression de sources
- **`users.py`** — gestion admin des comptes (liste, mise à jour de rôle, suppression)
- **`analytics.py`** — `GET /analytics/stats` et `GET /analytics/ai-metrics`

### Composant central : le streaming RAG

L'endpoint `POST /v1/ask/stream` (`routers/ai.py`, lignes 26-118) illustre la densité technique du projet. Son fonctionnement en cinq étapes est entièrement implémenté :

1. **Vérification d'accès** (lignes 40-49) : récupération de l'utilisateur depuis le JWT, vérification d'existence de la session, vérification d'ownership (un client ne peut accéder qu'à ses propres sessions, lignes 46-47 : `if not is_admin_or_sav(user) and session.id_utilisateur != user.id: raise HTTPException(404)`).

2. **Persistance de la question** (ligne 51) : le message utilisateur est sauvegardé avec `type_envoyeur="user"` avant tout appel à l'IA, garantissant la traçabilité même en cas d'erreur dans les étapes suivantes.

3. **Retrieval RAG** (lignes 63-69) : la question est vectorisée par `embed_text()`, puis pgvector retourne les `KB_TOP_K` chunks les plus proches par distance cosinus HNSW. Le contexte est tronqué à `KB_MAX_CONTEXT_CHARS` caractères (configurable via variable d'environnement).

4. **Génération streamée** (lignes 82-116) : le générateur Python `stream_tokens()` itère sur les tokens produits par `stream_text(prompt, model=MISTRAL_MODEL)` et les `yield` au fur et à mesure via `StreamingResponse(stream_tokens(), media_type="text/plain")`. La réponse n'est donc jamais entièrement chargée en mémoire.

5. **Logging de monitoring** (lignes 103-115) : dans le bloc `finally` du générateur — garantissant l'exécution même en cas d'exception — un enregistrement `AICallLog` est créé avec la latence mesurée (`int((time.perf_counter() - t_start) * 1000)`), le nombre de chunks trouvés et le statut succès/erreur.

### Sécurité : implémentation multicouche

La sécurité est implémentée en profondeur, depuis le transport jusqu'à la donnée.

**Authentification JWT** : le token HS256 est signé avec `SECRET_KEY` (générée automatiquement sur Render, `render.yaml` ligne 21 : `generateValue: true`) et expire après `ACCESS_TOKEN_EXPIRE_MINUTES` minutes (60 par défaut, `dependencies.py` ligne 17). La fonction `get_current_user()` (`dependencies.py`, lignes 72-87) accepte le token soit depuis le header `Authorization: Bearer`, soit depuis le cookie `auth_token`. Ce double mode est essentiel pour la gestion SSE, qui ne supporte pas nativement les headers dans certains contextes navigateur.

**Cookies httpOnly SameSite=strict** : les tokens d'authentification sont émis dans des cookies httpOnly, empêchant leur lecture par JavaScript et protégeant contre les attaques XSS (implémenté dans `routers/auth.py`).

**RBAC 4 niveaux** : la fonction `is_admin_or_sav()` (`dependencies.py`, lignes 97-100) est injectée comme dépendance FastAPI sur toutes les routes d'administration. La vérification d'ownership est systématisée : la session ou la ressource demandée est filtrée côté serveur avec l'identifiant extrait du JWT, jamais depuis un paramètre client.

**Hachage des mots de passe** : bcrypt via `passlib.CryptContext` (`dependencies.py`, ligne 12). La réponse de l'endpoint `POST /v1/register` exclut explicitement `password_hash` — vérifié par le test `test_api.py`, ligne 25 : `assert "password_hash" not in data`.

**Sanitisation** : la fonction `sanitize_text()` (`dependencies.py`, ligne 45) supprime les null bytes (`\x00`) et les caractères de contrôle. Une sanitisation plus complète (suppression de 14 catégories de caractères de contrôle, normalisation des espaces) est appliquée dans le pipeline d'ingestion (`ingest_postgres.py`, lignes 50-54).

**CORS** : les origines autorisées sont lues depuis `CORS_ORIGINS` en variable d'environnement (`main.py`, lignes 43-51). En production (Render), seule l'URL du frontend est autorisée (`render.yaml`, ligne 27 : `value: "https://smartticket-frontend.onrender.com"`).

[CAPTURE : extrait de `dependencies.py` — fonctions `get_current_user()` et `is_admin_or_sav()` annotées]

### Conformité RGPD

La conformité RGPD est implémentée à trois niveaux. Au niveau du **schéma de données**, les tables `utilisateur` et `chat_sessions` possèdent une colonne `deleted_at TIMESTAMPTZ` (`models.py`, lignes 25 et 37) : toutes les requêtes de lecture filtrent sur `deleted_at IS NULL`, rendant les données "supprimées" invisibles sans les effacer physiquement. Au niveau de la **purge automatique**, un job APScheduler est démarré au démarrage de l'application (`main.py`, ligne 174 : `scheduler.add_job(purge_soft_deleted, "cron", hour=3, minute=0, id="rgpd_purge")`). La fonction `purge_soft_deleted()` (lignes 65-90) hard-delete les utilisateurs et sessions dont `deleted_at` est antérieur au seuil de rétention, paramétrable via `PURGE_RETENTION_DAYS` (30 jours par défaut). La purge est également déclenchée immédiatement au démarrage (ligne 178) pour traiter les enregistrements déjà expirés. Au niveau du **droit à la portabilité** (Article 20 RGPD), un endpoint `GET /v1/me/export` est documenté dans le `CHANGELOG.md` (ligne 39).

[CAPTURE : code de `purge_soft_deleted()` dans `main.py` lignes 65-90 — annoté avec le flux soft-delete → retention → hard-delete]

### Interface frontend : le composant de chat en streaming

Côté frontend, le composant `/ai-assistant/[id]` (`frontend/app/(chat)/ai-assistant/[id]/page.tsx`) gère l'affichage du stream Mistral token par token. La route `/api/ask` (`frontend/app/api/ask/route.ts`) proxifie la requête vers le backend en passant le cookie d'authentification, puis retransmet le stream SSE au client. La bibliothèque `streamdown` (version 2.4.0, `package.json`) assure le rendu incrémental du Markdown sans re-render global de l'interface à chaque token.

Les dashboards admin et SAV (`components/dashboard/AdminDashboard.tsx`, `SavDashboard.tsx`) utilisent Recharts (version ^3.6.0) pour les visualisations. Les interfaces sont construites avec les composants Shadcn UI et Radix UI, qui fournissent des primitives accessibles by default (focus management, aria roles, keyboard navigation).

### Points faibles à renforcer

Plusieurs lacunes de sécurité OWASP sont connues et non adressées en V1 : **absence de rate limiting** (vulnérabilité brute force sur `POST /v1/login`), **absence de headers de sécurité** (CSP, X-Frame-Options, HSTS non configurés au niveau applicatif — dépendent d'un reverse proxy non présent en V1), **absence de refresh token** (JWT à durée fixe sans rotation), **absence de validation de la taille des fichiers uploadés** avant traitement. Ces lacunes sont connues et listées dans `docs/E4/C15/01_specifications_techniques.md`.

---

## 6. C18 — Automatiser les tests via l'intégration continue

> **Libellé officiel :** Automatiser les phases de tests du code source lors du versionnement des sources à l'aide d'un outil d'intégration continue de manière à garantir la qualité technique des réalisations.

### Pipeline CI : architecture des trois jobs

Le workflow GitHub Actions est défini dans `.github/workflows/ci.yml` (181 lignes). Il se déclenche sur tout push et pull request ciblant la branche `main` (lignes 3-7). Trois jobs sont définis :

**Job 1 — `backend-tests`** (lignes 13-93) : exécuté sur `ubuntu-latest`, il démarre un service PostgreSQL `pgvector/pgvector:pg18` (lignes 17-30) avec health check (`pg_isready`) — ce n'est pas une base mockée mais une instance réelle de la même image que la production. Le job enchaîne : installation des dépendances (`requirements.txt` + `requirements-dev.txt`), lint Ruff, exécution de pytest avec coverage, génération d'un résumé Markdown dans le Step Summary GitHub. Les artefacts `test-results.xml` (JUnit) et `coverage.xml` (Cobertura) sont publiés via `actions/upload-artifact@v4` (lignes 86-93).

**Job 2 — `frontend-tests`** (lignes 98-145) : sur `ubuntu-latest`, il enchaîne `npm ci`, vérification des types TypeScript (`tsc --noEmit`, ligne 119), analyse ESLint avec tolérance zéro (`--max-warnings 0`, ligne 123), exécution Jest avec coverage, et build de production Next.js. Le build en CI garantit que l'application est compilable et que les routes dynamiques sont correctement définies.

**Job 3 — `deploy`** (lignes 152-181) : déclenché uniquement si les deux premiers jobs sont verts (`needs: [backend-tests, frontend-tests]`, ligne 155) et uniquement sur un push sur `main` (`if: github.ref == 'refs/heads/main' && github.event_name == 'push'`, ligne 156). Il envoie les deploy hooks Render via `curl` pour le backend et le frontend.

[CAPTURE : capture d'écran GitHub Actions — liste des runs récents avec les 3 jobs (Backend / Frontend / Déploiement) en vert]

### Lint : configuration et règles

La configuration Ruff est définie dans `backend/pyproject.toml` (31 lignes). Quatre familles de règles sont activées : `E` (pycodestyle errors), `W` (pycodestyle warnings), `F` (pyflakes — imports inutilisés, variables non utilisées), `I` (isort — ordre des imports). Quelques règles sont désactivées de manière explicitement justifiée : `E501` (longueur de ligne, gérée par `line-length = 100`), `E402` (import pas en tête de fichier, intentionnel pour `load_dotenv()` avant les imports de modules utilisant les variables d'env), `E712` (comparaison `== True` / `== False`, requis par les filtres SQLAlchemy ORM). Cette granularité dans la configuration montre une maîtrise de l'outil plutôt qu'une configuration par défaut.

La commande CI est `ruff check .` (`.github/workflows/ci.yml`, ligne 53), sans flags permissifs : tout warning est bloquant.

Côté frontend, ESLint est configuré dans `frontend/eslint.config.mjs` avec les règles TypeScript strict. La commande CI `npx eslint app components hooks lib --ext .ts,.tsx --max-warnings 0` est également bloquante à zéro warning.

### Suite de tests backend

La suite de tests backend est organisée en quatre fichiers dans `backend/tests/` :

**`test_api.py`** — tests d'intégration couvrant les endpoints métier : authentification (inscription avec doublons email/username, connexion correcte, mauvais mot de passe), profil (`GET /me`, `PUT /me`), sessions (création, liste, clôture, transfert), messages (création, liste, feedback). La fixture `conftest.py` fournit un client HTTP TestClient `httpx`, un client authentifié (`auth_client`), un utilisateur enregistré (`registered_user`), et un client admin. La ligne 25 de `test_api.py` (`assert "password_hash" not in data`) vérifie explicitement que la réponse d'inscription n'expose pas le hash.

**`test_analytics.py`** — tests du contrôle d'accès (401 non authentifié, 403 rôle insuffisant) et de la structure des réponses JSON des endpoints `/v1/analytics/stats` et `/v1/analytics/ai-metrics`. La classe `TestAnalyticsAuth` (lignes 34-52) garantit que ces endpoints critiques sont inaccessibles sans authentification et sans rôle admin/SAV.

**`test_rag_evaluation.py`** — évaluation de la qualité du pipeline RAG : pertinence des embeddings, taux de chunks trouvés sur des questions de test représentatives.

**`test_utils.py`** — tests des fonctions utilitaires (sanitize_text, chunk_text, build_rag_prompt).

Les tests s'exécutent contre une vraie base PostgreSQL+pgvector en CI (pas de mock), ce qui garantit que les comportements testés correspondent exactement aux comportements de production, notamment les opérations vectorielles et les contraintes de schéma.

[CAPTURE : output `pytest -v` depuis les logs GitHub Actions — liste des tests avec PASSED/FAILED]

### Couverture de code

La couverture est mesurée par `pytest-cov` et reportée en CI sous deux formats : `term-missing` dans les logs (liste des lignes non couvertes) et `coverage.xml` publié comme artefact. La commande exacte est :

```
pytest tests/ -v --tb=short \
  --cov=. --cov-report=term-missing --cov-report=xml \
  --junit-xml=test-results.xml
```

À COMPLÉTER : le taux de couverture exact n'a pas été mesuré et archivé dans un rapport accessible depuis ce document. Pour la soutenance, récupérer le pourcentage depuis l'artifact `coverage.xml` du dernier run CI réussi.

### Points faibles à renforcer

L'absence de tests d'intégration bout en bout (frontend → backend) est la lacune principale. Les tests Jest frontend sont limités à des tests unitaires de fonctions utilitaires et de proxy API (`__tests__/api.test.ts`, `__tests__/utils.test.ts`) sans tester les composants React ou les flux utilisateurs complets. Il n'y a pas de tests de contrat (Pact), pas de tests de performance, et pas de scans de sécurité automatisés (SAST, dependency vulnerability scan comme `safety` ou `npm audit`) dans le pipeline CI.

---

## 7. C19 — Créer un processus de livraison continue

> **Libellé officiel :** Créer un processus de livraison continue d'une application en s'appuyant sur une chaîne d'intégration continue et en paramétrant les outils d'automatisation et les environnements de test afin de permettre une restitution optimale de l'application.

### Infrastructure as Code : render.yaml

La définition de l'infrastructure de production est entièrement déclarative dans `render.yaml` (48 lignes). Ce fichier constitue l'IaC du projet : il décrit deux services web Docker et une base PostgreSQL managée, avec leurs variables d'environnement respectives.

Le service backend (`smartticket-backend`) est configuré avec un `healthCheckPath: /` (ligne 14), ce qui signifie que Render valide la disponibilité du service via `GET /` avant de router le trafic vers le nouveau déploiement. Le handler correspondant dans `main.py` (ligne 183-185) retourne `{"status": "Online"}`. En cas d'échec du health check, Render maintient l'ancienne version en service — comportement de rollback automatique sans configuration additionnelle.

La variable `SECRET_KEY` est générée automatiquement par Render à la création du service (`generateValue: true`, ligne 21), éliminant le risque de stocker un secret dans le dépôt. La variable `MISTRAL_API_KEY` est marquée `sync: false` (ligne 29), indiquant qu'elle doit être saisie manuellement dans le dashboard Render et ne sera jamais écrite dans le dépôt. La `DATABASE_URL` est injectée automatiquement depuis la base managée via `fromDatabase.connectionString` (lignes 17-19), garantissant la cohérence entre le service et sa base sans gestion manuelle de chaîne de connexion.

```yaml
# render.yaml, lignes 16-19 — injection automatique de la DATABASE_URL
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: smartticket-postgres
      property: connectionString
```

[CAPTURE : `render.yaml` complet annoté — avec flèches montrant les injections automatiques (DATABASE_URL, SECRET_KEY)]

### Deux environnements cohérents

Le projet maintient deux environnements dont la cohérence est garantie par l'utilisation des mêmes Dockerfiles :

**Environnement de développement local** (`docker-compose.yml`, 111 lignes) : 6 services sont orchestrés — `backend` (port 8000), `frontend` (port 3005), `postgres` avec pgvector (port 5432, le DDL `init-db.sql` est monté dans `/docker-entrypoint-initdb.d/`), `pgadmin` (port 5050), `ollama` (port 11434, service IA local), `ollama-webui` (port 3002). Redis est présent dans le compose mais non utilisé dans la V1 du code (présence conservée pour la V2). En développement, le service IA est Ollama (modèle local) et non l'API Mistral, permettant de tester sans consommer de tokens API.

**Environnement de pré-production/production** (`render.yaml`) : le même `backend/Dockerfile` et `frontend/Dockerfile` sont utilisés, garantissant la parité d'image. Le service Ollama est absent (remplacé par l'API Mistral), et la base PostgreSQL est managée par Render (backup automatique, haute disponibilité).

Cette distinction entre les deux environnements est une décision documentée dans `docs/E4/C15/04_poc_preproduction.md` : l'environnement local inclut des outils de développement (pgAdmin, Ollama WebUI) absents de la production, mais les composants applicatifs (backend, frontend, postgres+pgvector) sont identiques.

### Pipeline de déploiement continu

Le pipeline CD complet, de `git push` à la mise en production, est le suivant :

1. `git push origin main` déclenche le workflow CI (`ci.yml`, lignes 3-7)
2. Jobs `backend-tests` et `frontend-tests` s'exécutent en parallèle
3. Si les deux jobs réussissent, le job `deploy` se déclenche (condition `needs: [backend-tests, frontend-tests]` + `github.ref == 'refs/heads/main'`)
4. Deux appels `curl` envoient les deploy hooks Render pour le backend et le frontend (lignes 161-168)
5. Render pull l'image Docker depuis le registry, build le container, démarre le service
6. Render valide le health check sur `GET /` avant de basculer le trafic
7. Les migrations de base de données s'exécutent automatiquement au démarrage de FastAPI (`main.py`, fonction `run_migrations()`, lignes 93-165) : création de l'extension `vector`, création des tables manquantes, `ALTER TABLE` idempotents pour les colonnes ajoutées progressivement

Ce point 7 mérite une attention particulière : les migrations sont idempotentes grâce aux gardes SQL (`CREATE EXTENSION IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). Il n'y a pas de gestionnaire de migrations dédié (Alembic n'est pas utilisé) : les migrations incrémentales sont exécutées au démarrage et leur idempotence est garantie par les clauses `IF NOT EXISTS`.

[CAPTURE : diagramme du pipeline CD — git push → GitHub Actions (3 jobs) → Render deploy hooks → Docker pull/build/start → health check → trafic routé]

### Containerisation

Le backend est containerisé depuis `python:3.11-slim` (`backend/Dockerfile`), image minimale réduisant la surface d'attaque. Le frontend est containerisé depuis `node:20-slim` (`frontend/Dockerfile`), avec le port exposé configurable via la variable `$PORT`, compatible avec les exigences Render. Les deux images sont buildées en CI dans le job frontend (`npm run build`, ligne 133 de `ci.yml`) pour valider que le build de production ne présente pas d'erreurs avant le déploiement.

### Points faibles à renforcer

L'infrastructure présente plusieurs limites inhérentes au tier free de Render : cold starts lors d'une période d'inactivité (~30 secondes de latence à la première requête), absence d'auto-scaling, pas de load balancer configuré. Ces limites sont assumées dans le contexte d'un projet de démonstration et documentées dans `docs/E4/C15/04_poc_preproduction.md`. Il n'y a pas de configuration de staging distinct : la branche `main` déploie directement en production. Une architecture plus robuste utiliserait une branche `staging` avec déploiement sur un environnement de validation avant promotion en production.

---

## 8. Synthèse

### Matrice de couverture des compétences

| Compétence | Libellé court | Documentation | Implémentation | Tests | CI/CD | Preuves principales |
|---|---|---|---|---|---|---|
| **C14** | Analyse besoin & specs | `docs/E4/C14/` (4 fichiers) | `models.py`, `init-db.sql` | conftest fixtures | — | 8 user stories avec critères WCAG, MCD Merise, matrice accessibilité |
| **C15** | Architecture & outils | `docs/E4/C15/` (5 fichiers) + `RAG_DECISIONS_LOG.md` | `ingest_postgres.py`, `routers/ai.py`, `next.config.ts` | — | — | 6 ADR documentés, diagrammes C4, justifications stack |
| **C16** | Coordination MLOps | `CHANGELOG.md`, `RAG_DECISIONS_LOG.md`, `AUDIT_E3.md` | `routers/analytics.py`, `models.py:AICallLog` | `test_analytics.py` | — | KB Health Score, alertes automatiques, 6 ADR avec métriques |
| **C17** | Développement & sécurité | `docs/E4/C14/04_accessibilite.md` | `routers/` (7 fichiers), `dependencies.py`, `main.py` | `test_api.py` (~25 tests) | lint bloquant | JWT+RBAC, RGPD purge job, streaming SSE, sanitisation |
| **C18** | Tests & CI | `.github/workflows/ci.yml` | `backend/tests/` (4 fichiers + conftest), `frontend/__tests__/` | pytest + jest | CI 3 jobs | pgvector réel en CI, Ruff + ESLint 0-warning, artifacts JUnit+Cobertura |
| **C19** | Déploiement continu | `docs/E4/C15/04_poc_preproduction.md` | `render.yaml`, `docker-compose.yml`, 2 Dockerfiles | — | CD conditionnel | IaC déclaratif, 2 environnements cohérents, migrations idempotentes, healthcheck |

### Points forts de la V1

**La cohérence entre les couches** est le point fort le plus notable du projet : les user stories (C14) définissent des critères d'acceptation de sécurité qui sont implémentés dans le code (C17) et vérifiés par des tests automatisés (C18) qui ne peuvent pas passer si la sécurité est cassée (test ligne 25 de `test_api.py`). Cette traçabilité verticale — de la spec au test en passant par le code — est ce que le jury cherche à évaluer.

**La démarche MLOps itérative**, même sans MLflow, est documentée avec une rigueur adaptée au contexte (API externe non entraînable) : le `RAG_DECISIONS_LOG.md` constitue un journal d'expériences avec signal déclencheur quantifié, action prise pointant vers le fichier et la ligne de code, mesure d'impact, et liste de pistes V2 avec conditions d'activation.

**L'IaC 100% déclarative** via `render.yaml` démontre une maîtrise du déploiement moderne : injection automatique de secrets générés, référence inter-ressources (`fromDatabase.connectionString`), health check configuré, deux environnements différenciés (local Ollama vs prod API Mistral) avec les mêmes images Docker.

### Limites assumées de la V1

Je reconnais trois limites significatives dans cette V1. Premièrement, **l'absence de tests d'accessibilité automatisés** : les critères WCAG sont spécifiés dans les user stories et documentés dans la matrice de conformité, mais ils ne sont pas vérifiés automatiquement dans le pipeline CI. Deuxièmement, **les lacunes de sécurité OWASP** connues (rate limiting, security headers, refresh tokens, audit log) : elles sont identifiées dans la documentation mais non implémentées, ce qui constitue une dette technique explicite. Troisièmement, **l'absence de staging** : le pipeline CD déploie directement sur la production sans environnement de validation intermédiaire.

### Perspectives V2

Cinq axes d'amélioration sont déjà formalisés dans `docs/E3/RAG_DECISIONS_LOG.md` avec leurs conditions d'activation : dédoublonnage des chunks par hash, quarantaine des chunks à feedback négatif répété, alertes actives (notifications push), index sur clés étrangères pour les performances de jointure, et évaluation automatique de la qualité de génération (benchmark questions/réponses). Ces pistes constituent une roadmap concrète ancrée dans les signaux de monitoring.

Sur l'infrastructure, la migration vers Kubernetes (Helm charts, HPA pour l'auto-scaling, PodDisruptionBudget pour le zéro-downtime) et l'ajout d'un environnement staging distinct avec promotion manuelle vers la production constitueraient les évolutions architecturales prioritaires pour industrialiser le projet.

---

*Rapport généré à partir de l'analyse directe du dépôt SmartTicket. Chaque affirmation est tracée vers un fichier, une ligne ou un commit du dépôt. Les éléments marqués "À COMPLÉTER" nécessitent une vérification manuelle avant la soutenance.*
