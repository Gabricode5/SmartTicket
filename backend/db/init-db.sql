-- =========================================
-- INIT BASE DE DONNEES - CRM + IA
-- =========================================

-- Active l'extension pgvector (type vector + index ANN) pour le RAG
CREATE EXTENSION IF NOT EXISTS vector;
-- Active pgcrypto pour hasher les mots de passe directement en SQL
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================
-- TABLE ROLES
-- =========================================
-- Table de référence des rôles applicatifs.
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,                 -- Identifiant du rôle
    nom_role VARCHAR(20) UNIQUE NOT NULL   -- Nom unique du rôle (user, ai, sav, admin)
);

-- Rôles par défaut.
-- ON CONFLICT évite l'erreur si le rôle existe déjà.
INSERT INTO roles (nom_role) VALUES ('user'), ('ai'), ('sav'), ('admin')
ON CONFLICT (nom_role) DO NOTHING;

-- =========================================
-- TABLE UTILISATEUR
-- =========================================
-- Comptes applicatifs.
CREATE TABLE utilisateur (
    id SERIAL PRIMARY KEY,                                   -- Identifiant du compte
    username VARCHAR(50) UNIQUE NOT NULL,                    -- Pseudo unique
    email VARCHAR(100) UNIQUE NOT NULL,                      -- Email unique
    password_hash TEXT NOT NULL,                             -- Mot de passe hashé (jamais en clair)
    prenom VARCHAR(50),                                      -- Prénom optionnel
    nom VARCHAR(50),                                         -- Nom optionnel
    id_role INTEGER REFERENCES roles(id) DEFAULT 1,          -- Rôle par défaut = user
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Date de création
);

-- =========================================
-- COMPTE ADMIN PAR DEFAUT (ENV DEV)
-- =========================================
-- Crée un compte admin initial:
-- username: admin
-- email: admin@admin.com
-- mot de passe: admin (hashé via bcrypt avec pgcrypto)
-- ON CONFLICT empêche un doublon si l'email existe déjà.
INSERT INTO utilisateur (username, email, password_hash, prenom, nom, id_role)
SELECT
    'admin',
    'admin@admin.com',
    crypt('admin', gen_salt('bf')),
    'Admin',
    'Local',
    r.id
FROM roles r
WHERE r.nom_role = 'admin'
ON CONFLICT (email) DO NOTHING;

-- =========================================
-- TABLE CHAT_SESSIONS
-- =========================================
-- Contient les conversations de chaque utilisateur.
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,                                    -- Identifiant de la session
    id_utilisateur INTEGER REFERENCES utilisateur(id) ON DELETE CASCADE, -- Propriétaire session
    title VARCHAR(255),                                       -- Titre session
    status VARCHAR(20) NOT NULL DEFAULT 'open',               -- Statut (open/closed)
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Date de création
);

-- =========================================
-- TABLE CHAT_MESSAGES
-- =========================================
-- Messages envoyés dans une session de chat.
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,                                   -- Identifiant message
    id_session INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE, -- Session liée
    type_envoyeur VARCHAR(10) CHECK (type_envoyeur IN ('user', 'ai', 'sav')), -- Qui envoie
    contenu TEXT NOT NULL,                                   -- Texte du message
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Date d'envoi
);

-- =========================================
-- TABLE KNOWLEDGE_BASE
-- =========================================
-- Base de connaissances vectorielle utilisée pour le RAG.
CREATE TABLE knowledge_base (
    id SERIAL PRIMARY KEY,                                    -- Identifiant chunk/document
    source_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL, -- Source optionnelle
    contenu TEXT NOT NULL,                                    -- Contenu textuel indexé
    embedding vector(1024),                                   -- Vecteur embedding (mistral-embed 1024)
    category VARCHAR(50),                                     -- Catégorie logique (ex: service-public)
    source VARCHAR(500),                                      -- Nom/fichier/source logique du document indexé
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Date d'insertion
);

-- Index HNSW pour accélérer la recherche vectorielle (similarité cosinus)
CREATE INDEX ON knowledge_base USING hnsw (embedding vector_cosine_ops);
