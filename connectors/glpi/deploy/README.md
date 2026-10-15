# Paquet d'installation — passerelle GLPI

Lance tout en une commande : la base vectorielle (pgvector) et la passerelle (web +
worker). Rien à installer ni configurer à côté.

## 1. Configuration

```bash
cp .env.example .env
```

Remplir dans `.env` : `GLPI_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`,
`MISTRAL_API_KEY`, `POSTGRES_PASSWORD`. `DRY_RUN=true` par défaut — aucune écriture
dans GLPI tant que tu ne le repasses pas à `false`.

## 2. Base de connaissances

Déposer les `.txt` dans `./faq/` (un fichier = un document source).

## 3. Lancement

```bash
docker compose up -d --build
docker compose exec gateway-web python -m glpi_connector.scripts.ingest_faq /app/faq --category faq
```

Le schéma (`knowledge_chunk`, `processed_tickets`) est créé automatiquement au premier
démarrage — rien à migrer à la main.

## Vérifier

```bash
curl http://localhost:8000/health
curl http://localhost:8000/admin/status
curl -X POST http://localhost:8000/admin/poll   # un seul passage, respecte DRY_RUN
```

## Dry-run → réel

`DRY_RUN=true` par défaut : `gateway-worker` logue ce qu'il posterait, sans appeler
GLPI. Une fois une suggestion vérifiée correcte (`docker compose logs gateway-worker`
ou `/admin/poll`), repasser `DRY_RUN=false` dans `.env` puis :

```bash
docker compose up -d
```
