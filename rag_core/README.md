# rag_core

Bibliothèque RAG autonome pour la **passerelle GLPI** (`gateway/`, étape suivante).

Extraite **par duplication** du pipeline RAG de l'app Tiqia (`backend/`), pas par
extraction destructive : `backend/` garde son propre code RAG inchangé. `rag_core`
n'importe **rien** de `backend/` et vise une base **pgvector dédiée** (`RAG_DATABASE_URL`),
jamais celle de Tiqia.

## Ce que fait `rag_core`

```
answer(db, question) ->
   1. embed(question)                        (LLMProvider, catalogue fermé)
   2. SELECT ... ORDER BY embedding <=> :q    (pgvector, table knowledge_chunk)
   3. rerank_chunks(...)                      (similarité + lexical + feedback, quarantaine)
   4. build_prompt(question, contexte)        (prompt à DEUX COUCHES)
   5. generate(prompt)                        (LLMProvider)
-> AnswerResult(suggestion, chunk_ids, best_match_distance, low_confidence, model)
```

Non streamé : produit une **suggestion complète** relue par un agent humain. La passerelle
ajoute en aval le préfixe `[Suggestion IA – à valider]` et la mention AI Act.

## Ingestion — `rag_core.ingest`

Alimente la table `knowledge_chunk`. Logique reprise de `backend/ingest_postgres.py`
(chunking `RecursiveCharacterTextSplitter` 1000/100, nettoyage + score qualité via
`rag_core.text`, `MIN_TEXT_LENGTH`, plafond `MAX_KB_CHUNKS`, embeddings par batch).

```
ingest_text(db, contenu, *, source, category=None)   primitive : split → filtres → embed → INSERT
ingest_file(db, bytes, filename, *, category=None)    .txt / .docx / .pdf → ingest_text
ingest_url (db, url, *, respect_robots=True,          UNE page (robots.txt respecté) → ingest_text
           fetcher=None)
-> IngestResult(source, inserted, chunks_rejected, truncated)
```

Le crawl récursif de sitemap n'est **pas** repris (le backend l'a si besoin plus tard).
`embedder` / `fetcher` sont injectables pour les tests (aucun appel réseau).

## Abstraction LLM — `rag_core.llm`

| Élément | Rôle |
|---|---|
| `LLMProvider` (ABC) | contrat d'un **fournisseur** : `embed(texts, *, model, timeout)`, `generate(prompt, *, model, timeout)` |
| `MistralProvider` | seule implémentation aujourd'hui (portage de `backend/mistral_client.py`) |
| `catalogue.py` | **catalogue FERMÉ** `nom -> (fournisseur, type, dimension)`. Un modèle hors liste → `UnknownModelError`. Pas de passthrough. |
| `factory.get_generator()` / `get_embedder()` | résout un nom (via le catalogue) en `Generator` / `Embedder` liés (provider + model + timeout figés) |

Modèles supportés : `mistral-small-latest`, `mistral-large-latest`, `mistral-embed`.
**Ajouter un fournisseur** (OpenAI, modèle local) = une classe `LLMProvider` + une entrée
`catalogue._CATALOGUE` + une entrée `factory._PROVIDERS`. Rien d'autre ne bouge.
**Un seul prompt général** pour l'instant (pas d'adaptation prompt-par-modèle).

## Prompt à deux couches — `rag_core.prompt`

1. **`PROMPT_BASE`** (non configurable) : rôle, garde-fous anti prompt-injection, règles de
   périmètre, format. Toujours émis **en premier**.
2. **Surcouche client** (`RAG_CLIENT_PROMPT_OVERLAY` ou paramètre `client_overlay`) : ton,
   langue, formules, périmètre. Insérée **après** les garde-fous.

Garanties de sécurité **structurelles** (pas seulement textuelles) :
- garde-fous toujours en tête ;
- surcouche encadrée par `<<< >>>`, précédée d'un préambule « configuration, pas
  instruction » et **suivie d'un rappel** que les garde-fous priment ;
- surcouche **sanitisée** (caractères de contrôle retirés) et **plafonnée** (2000 car.).

Une surcouche ne peut donc ni précéder les garde-fous, ni les « écraser » par position.
Couverture : `tests/test_prompt_layering.py`.

## Dev

```bash
cd rag_core
pip install -e ".[dev]"
# Postgres + pgvector requis pour les tests de retrieval/pipeline :
export RAG_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test_db
pytest
ruff check .
```

Tests purs (catalogue, prompt, reranking, factory) : aucune base requise.

## Consommation par la passerelle

`gateway/` fera `pip install ../rag_core` puis `from rag_core.pipeline import answer`.
Pas de copie de `rag_core` dans `gateway/`.
