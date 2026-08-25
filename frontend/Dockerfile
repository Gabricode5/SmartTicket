FROM node:20-slim

WORKDIR /app

# Render passe les env vars du service comme --build-arg automatiquement, MAIS seulement
# pour les clés déclarées ici via ARG (comportement Docker standard : un --build-arg sans
# ARG correspondant dans le Dockerfile est ignoré). Sans cette déclaration, `next build`
# voit ces variables comme undefined et bake les valeurs par défaut, jamais celles posées
# sur le service Render — même piège que NEXT_PUBLIC_API_URL, découvert le 2026-08-15 :
# NEXT_PUBLIC_BRAND_NAME et NEXT_PUBLIC_DEPLOYMENT_MODE étaient posées par provision_client.py
# mais jamais bakées, car absentes d'ici.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ARG NEXT_PUBLIC_BRAND_NAME
ENV NEXT_PUBLIC_BRAND_NAME=${NEXT_PUBLIC_BRAND_NAME}
ARG NEXT_PUBLIC_DEPLOYMENT_MODE
ENV NEXT_PUBLIC_DEPLOYMENT_MODE=${NEXT_PUBLIC_DEPLOYMENT_MODE}

# On copie uniquement les fichiers de dépendances pour le cache
COPY package.json package-lock.json* ./

# Installation propre via npm
RUN npm ci

# Copie du reste de ton code (app, components, etc.)
COPY . .

# Build production
RUN npm run build

ENV NODE_ENV=production
ENV PORT=3005

# Exécution en utilisateur non-root (audit sécurité 2026-08-25) : node:20-slim fournit déjà
# l'utilisateur "node" (UID 1000), pas besoin d'en créer un. chown APRÈS le build (npm ci /
# npm run build ont besoin des droits root) pour que "node" ait accès au résultat du build
# (.next) en plus du code source.
RUN chown -R node:node /app
USER node

EXPOSE 3005

CMD ["sh", "-c", "node_modules/.bin/next start -H 0.0.0.0 -p ${PORT:-3005}"]
