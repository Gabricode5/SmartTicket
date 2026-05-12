
# SmartTicket

Application de gestion de tickets avec :

- un frontend `Next.js`
- un backend `FastAPI`
- une base `PostgreSQL` avec `pgvector`
- des services Docker pour l'environnement local

## Structure

```text
frontend/   Interface utilisateur Next.js
backend/    API FastAPI, modèles et ingestion
docs/       Documents de projet
```

## Démarrage rapide

### 1. Pré-requis

- Docker et Docker Compose
- un fichier `.env` à la racine pour le backend

### 2. Lancer le projet

```bash
docker compose up -d --build
```

Pour suivre les logs :

```bash
docker compose up
```

Pour arrêter les services :

```bash
docker compose down
```

Pour arrêter les services et supprimer les données persistantes :

```bash
docker compose down -v
```

Attention : `docker compose down -v` supprime notamment les données PostgreSQL persistées.

## Services disponibles

| Service | URL | Description |
|---|---|---|
| Frontend | [http://localhost:3005](http://localhost:3005) | Interface utilisateur |
| Backend API | [http://localhost:8000](http://localhost:8000) | API FastAPI |
| Swagger | [http://localhost:8000/docs](http://localhost:8000/docs) | Documentation interactive |
| Open WebUI | [http://localhost:3002](http://localhost:3002) | Interface de test pour Ollama |
| pgAdmin | [http://localhost:5050](http://localhost:5050) | Administration PostgreSQL |
| Ollama | [http://localhost:11434](http://localhost:11434) | API du moteur LLM |

Identifiants `pgAdmin` par défaut :

- email : `admin@admin.com`
- mot de passe : `admin`

## Base de données PostgreSQL

Paramètres de connexion pour `pgAdmin` ou un client SQL :

| Paramètre | Valeur |
|---|---|
| Host | `postgres` |
| Port | `5432` |
| Database | `ticketdb` |
| Username | `admin` |
| Password | `Password1234` |

Le nom de connexion affiché dans votre client peut être choisi librement.

## Commandes utiles

Reconstruire les images :

```bash
docker compose up -d --build
```

Lister les modèles Ollama installés :

```bash
docker exec -it ticket-ai-ollama ollama list
```

Relancer uniquement le service Ollama :

```bash
docker compose up -d --force-recreate ollama
```

## Développement frontend

Si vous travaillez directement dans `frontend/` sans Docker :

```bash
cd frontend
npm install
npm run dev
```

## Déploiement

Le dépôt contient un fichier [`render.yaml`](./render.yaml) pour le déploiement des services.

## Notes

- Le frontend écoute sur le port `3005` en local.
- Le backend écoute sur le port `8000`.
- L'initialisation de la base est gérée par [`backend/db/init-db.sql`](./backend/db/init-db.sql).

## Conformité RGPD

### Données collectées

| Donnée | Table | Finalité |
|---|---|---|
| Email | `utilisateur` | Authentification, identifiant unique |
| Username | `utilisateur` | Affichage, identification interne |
| Prénom / Nom | `utilisateur` | Optionnels, personnalisation de l'interface |
| Mot de passe | `utilisateur` | Hashé (bcrypt) — jamais stocké en clair |
| Messages de chat | `chat_messages` | Historique de la conversation SAV |

Aucune donnée n'est transmise à des tiers, à l'exception des messages envoyés à l'API Mistral pour la génération de réponses IA.

### Mesures de sécurité techniques

| Mesure | Implémentation |
|---|---|
| Hachage des mots de passe | bcrypt via `passlib` (backend) et `pgcrypto` (SQL) |
| Token d'authentification | JWT signé avec expiration configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| Cookie sécurisé | `httpOnly`, `SameSite=strict` — protège contre le vol de session (XSS) |
| Suppression en cascade | `ON DELETE CASCADE` sur toutes les clés étrangères — la suppression d'un compte efface toutes ses données |
| Contrôle d'accès | Rôles `user` / `sav` / `admin` — chaque route vérifie les droits avant d'exécuter |
| Secrets externalisés | Variables d'environnement via `.env` (non commité dans git) |

### Droits des utilisateurs

- **Droit d'accès** : `GET /me` retourne les données du compte connecté.
- **Droit de rectification** : `PUT /me` permet de modifier username, email, prénom, nom.
- **Droit à l'effacement** : `DELETE /users/{id}` supprime le compte et toutes ses données associées (messages, sessions) grâce aux cascades SQL.
- **Consentement** : case à cocher obligatoire lors de l'inscription.

### Conservation des données

Les données sont conservées tant que le compte utilisateur existe. Aucune suppression automatique n'est configurée. La suppression du compte (`DELETE /users/{id}`) efface immédiatement toutes les données associées.
