# connectors/glpi

Passerelle **GLPI ↔ `rag_core`**. Un ticket créé dans GLPI (côté client) est récupéré par
polling, `rag_core.pipeline.answer` produit une **suggestion**, postée en **suivi
`ITILFollowup` privé** préfixé `[Suggestion IA - à valider]`. Un agent humain valide,
édite, envoie. **L'IA ne répond jamais en autonomie au client final.**

Cible de production : **on-premise chez le client** (Docker Compose sur leur infra, GLPI
joignable en réseau local). `render.yaml` ici = **dev/test uniquement** (GLPI Docker local).

## Rapport avec `rag_core`

Consommé **par dépendance**, jamais par copie : `pip install ../../rag_core` (ou
`pip install ./rag_core ./connectors/glpi` en CI/Docker). `connectors/glpi/` ne contient
aucune ligne de RAG — retrieval, reranking, prompt à deux couches, LLM : tout vient de
`rag_core`.

## Modules

| Module | Rôle |
|---|---|
| `config.py` | tous les réglages en env, **defaults prudents** : GLPI 10.x, `ITILFollowup`, `is_private=true`, préfixe `[Suggestion IA - à valider]`, `DRY_RUN=true` (strict), `RESPONSE_MODE=suggested` (seul autorisé — sinon erreur au démarrage) |
| `glpi_client.py` | `initSession` / `killSession`, `get_ticket`, `list_tickets` (filtre statut), `add_followup` (**seul appel d'écriture**). Transport HTTP injectable. |
| `store.py` + `models.py` | table `processed_tickets` : `is_processed` (garde avant traitement) + `record`. État en base → **aucun retraitement après redémarrage du worker**. |
| `poller.py` | `run_once(db, client, *, dry_run, answer_fn)` : liste tickets → skip déjà traités → suggestion → **DRY_RUN : log seul** / réel : `add_followup` → `record`. |
| `worker.py` | `python -m glpi_connector.worker` : session GLPI + boucle `run_once` toutes `POLL_INTERVAL_SECONDS`. |
| `main.py` | FastAPI : `GET /health`, `GET /admin/status`, `POST /admin/poll`. |

## DRY_RUN (strict)

`DRY_RUN=true` par défaut. **Seule** la valeur littérale `false` (insensible à la casse) le
désarme — toute autre valeur (vide, `0`, faute de frappe) laisse le dry-run actif. En
dry-run, `poller.run_once` **n'appelle jamais** `client.add_followup` : il logue le suivi
qu'il posterait et inscrit `processed_tickets.status = "dry_run"`. Vérifié par
`tests/test_poller.py::test_dry_run_never_calls_glpi_write`.

## Dev / tests

```bash
cd connectors/glpi
pip install -e ../../rag_core -e ".[dev]"
export CONNECTOR_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/connector_test
pytest                       # fixtures JSON GLPI + Postgres pour processed_tickets
ruff check .
```

`glpi_client` est testé contre des **fixtures JSON** (`tests/fixtures/`), sans instance
GLPI réelle.
