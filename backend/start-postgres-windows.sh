#!/bin/bash

# 1. Mot de passe requis explicitement — jamais de valeur par défaut en dur ici.
#    Usage : POSTGRES_PASSWORD=ton-mot-de-passe ./start-postgres-windows.sh
: "${POSTGRES_PASSWORD:?Définis POSTGRES_PASSWORD avant de lancer ce script (ex: POSTGRES_PASSWORD=... ./start-postgres-windows.sh)}"

# 2. First, create the network if it doesn't already exist
docker network create ticket-ai-network 2>/dev/null || true

# 3. Run the PostgreSQL container
# Note: MSYS_NO_PATHCONV=1 is used to prevent Git Bash on Windows from auto-converting Unix-style paths (like /var/lib/postgresql/data)
MSYS_NO_PATHCONV=1 docker run -d \
  --name ticket-ai-postgres \
  --restart unless-stopped \
  --network ticket-ai-network \
  -e POSTGRES_DB=ticketdb \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -p 5432:5432 \
  -v "$(pwd)/data/postgres:/var/lib/postgresql/data" \
  -v "$(pwd)/backend/db/init-db.sql:/docker-entrypoint-initdb.d/init.sql" \
  pgvector/pgvector:pg18
