FROM python:3.11-slim

WORKDIR /app

# Dépendances système pour Postgres
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000


# --proxy-headers : fait confiance aux en-têtes X-Forwarded-For envoyés par le
# reverse proxy de Render, sinon le rate limiting par IP (slowapi) verrait
# toujours l'IP interne du load balancer au lieu de celle du client.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
