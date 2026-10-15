# Contexte de build = RACINE du repo (pour COPY rag_core/ + connectors/glpi/).
#   docker build -f connectors/glpi/Dockerfile -t glpi-connector .
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# rag_core est consommé par DÉPENDANCE (installé), jamais copié dans le paquet connecteur.
COPY rag_core/ ./rag_core/
COPY connectors/glpi/ ./connectors/glpi/
RUN pip install --no-cache-dir ./rag_core ./connectors/glpi

RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Deux entrées possibles depuis la même image :
#   web    : uvicorn glpi_connector.main:app   (health check + admin)
#   worker : python -m glpi_connector.worker   (boucle de polling)
CMD ["sh", "-c", "uvicorn glpi_connector.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
