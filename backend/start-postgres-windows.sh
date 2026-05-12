#!/bin/bash

# 1. First, create the network if it doesn't already exist
docker network create ticket-ai-network 2>/dev/null || true

# 2. Run the PostgreSQL container
# Note: MSYS_NO_PATHCONV=1 is used to prevent Git Bash on Windows from auto-converting Unix-style paths (like /var/lib/postgresql/data)
MSYS_NO_PATHCONV=1 docker run -d \
  --name ticket-ai-postgres \
  --restart unless-stopped \
  --network ticket-ai-network \
  -e POSTGRES_DB=ticketdb \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=Password1234 \
  -p 5432:5432 \
  -v "$(pwd)/data/postgres:/var/lib/postgresql/data" \
  -v "$(pwd)/backend/db/init-db.sql:/docker-entrypoint-initdb.d/init.sql" \
  pgvector/pgvector:pg16
