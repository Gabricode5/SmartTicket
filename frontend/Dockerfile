FROM node:20-slim

WORKDIR /app

# Permet d'injecter l'URL API au moment du build
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# On copie uniquement les fichiers de dépendances pour le cache
COPY package.json package-lock.json* ./

# Installation propre via npm
RUN npm ci

# Copie du reste de ton code (app, components, etc.)
COPY . .

# Build production
RUN npm run build

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

EXPOSE 3000

CMD ["npm", "run", "start"]
