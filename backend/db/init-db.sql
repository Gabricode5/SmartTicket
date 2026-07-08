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
    nom_role VARCHAR(20) UNIQUE NOT NULL   -- Nom unique du rôle (user, ai, sav, superviseur, admin)
);

-- Rôles par défaut.
-- ON CONFLICT évite l'erreur si le rôle existe déjà.
INSERT INTO roles (nom_role) VALUES ('user'), ('ai'), ('sav'), ('superviseur'), ('admin')
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
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,           -- Email confirmé via le lien envoyé à l'inscription
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001', -- Préparation multi-tenant (valeur fixe, une instance = un tenant aujourd'hui)
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Date de création
    deleted_at TIMESTAMP WITH TIME ZONE                      -- Soft-delete RGPD (NULL = compte actif)
);
CREATE INDEX ON utilisateur (tenant_id);

-- =========================================
-- COMPTE ADMIN PAR DEFAUT (ENV DEV)
-- =========================================
-- Crée un compte admin initial:
-- username: admin
-- email: admin@admin.com
-- mot de passe: admin (hashé via bcrypt avec pgcrypto)
-- ON CONFLICT empêche un doublon si l'email existe déjà.
INSERT INTO utilisateur (username, email, password_hash, prenom, nom, id_role, email_verified)
SELECT
    'admin',
    'admin@admin.com',
    crypt('admin', gen_salt('bf')),
    'Admin',
    'Local',
    r.id,
    TRUE
FROM roles r
WHERE r.nom_role = 'admin'
ON CONFLICT (email) DO NOTHING;

-- =========================================
-- TABLE CHAT_SESSIONS
-- =========================================
-- Contient les conversations de chaque utilisateur.
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,                                    -- Identifiant de la session
    id_utilisateur INTEGER NOT NULL REFERENCES utilisateur(id) ON DELETE CASCADE, -- Propriétaire session
    title VARCHAR(255),                                       -- Titre session
    status VARCHAR(20) NOT NULL DEFAULT 'open',               -- Statut (open/transferred/closed)
    transfer_reason VARCHAR(50),                              -- Raison du transfert (technique/complexe/sensible/autre)
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001', -- Préparation multi-tenant
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Date de création
    deleted_at TIMESTAMP WITH TIME ZONE                       -- Soft-delete RGPD (NULL = session active)
);
CREATE INDEX ON chat_sessions (tenant_id);

-- =========================================
-- TABLE CHAT_MESSAGES
-- =========================================
-- Messages envoyés dans une session de chat.
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,                                   -- Identifiant message
    id_session INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE, -- Session liée
    type_envoyeur VARCHAR(10) CHECK (type_envoyeur IN ('user', 'ai', 'sav')), -- Qui envoie
    contenu TEXT NOT NULL,                                   -- Texte du message
    feedback INTEGER,                                        -- Retour utilisateur sur une réponse IA (1=👍, -1=👎, NULL=aucun)
    source_kb_ids INTEGER[],                                 -- Chunks knowledge_base.id utilisés pour générer cette réponse IA (reranking/feedback)
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001', -- Préparation multi-tenant
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Date d'envoi
);
CREATE INDEX ON chat_messages (tenant_id);

-- =========================================
-- TABLE AI_CALL_LOGS
-- =========================================
-- Journal des appels au modèle IA, utilisé par les dashboards monitoring/analytics.
CREATE TABLE ai_call_logs (
    id SERIAL PRIMARY KEY,                                    -- Identifiant du log
    id_session INTEGER REFERENCES chat_sessions(id) ON DELETE SET NULL, -- Session liée (optionnelle)
    call_type VARCHAR(20) NOT NULL,                           -- Type d'appel (ex: stream)
    model_name VARCHAR(100) NOT NULL,                         -- Modèle Mistral utilisé
    latency_ms INTEGER,                                       -- Latence de l'appel en millisecondes
    rag_chunks_found INTEGER,                                 -- Nombre de chunks RAG trouvés
    rag_context_chars INTEGER,                                -- Taille du contexte RAG injecté (caractères)
    success BOOLEAN NOT NULL DEFAULT TRUE,                    -- Succès ou échec de l'appel
    error_type VARCHAR(100),                                  -- Type d'erreur si échec
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001', -- Préparation multi-tenant
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Date de l'appel
);
CREATE INDEX ON ai_call_logs (tenant_id);

-- =========================================
-- TABLE KNOWLEDGE_BASE
-- =========================================
-- Base de connaissances vectorielle utilisée pour le RAG.
CREATE TABLE knowledge_base (
    id SERIAL PRIMARY KEY,                                    -- Identifiant chunk/document
    source_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL, -- Source optionnelle
    contenu TEXT NOT NULL,                                    -- Contenu textuel indexé
    embedding vector(1024) NOT NULL,                          -- Vecteur embedding (mistral-embed 1024)
    category VARCHAR(50),                                     -- Catégorie logique (ex: service-public)
    source VARCHAR(500),                                      -- Nom/fichier/source logique du document indexé
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001', -- Préparation multi-tenant (table des chunks vectoriels — la plus sensible en cas de future bascule multi-tenant)
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Date d'insertion
);

-- Index HNSW pour accélérer la recherche vectorielle (similarité cosinus)
CREATE INDEX ON knowledge_base USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON knowledge_base (tenant_id);

-- =========================================
-- TABLE NOTIFICATIONS
-- =========================================
-- Notifications in-app (réponse SAV sur un ticket, ticket transféré vers l'équipe humaine).
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,                                    -- Identifiant notification
    id_utilisateur INTEGER NOT NULL REFERENCES utilisateur(id) ON DELETE CASCADE, -- Destinataire
    id_session INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE, -- Ticket concerné (optionnel)
    type VARCHAR(30) NOT NULL,                                -- sav_reply | session_transferred
    message VARCHAR(255) NOT NULL,                            -- Texte affiché
    read_at TIMESTAMP WITH TIME ZONE,                         -- NULL = non lue
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001', -- Préparation multi-tenant
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Accélère le badge "non lues" (requête la plus fréquente, en polling côté frontend)
CREATE INDEX ON notifications (id_utilisateur, read_at);
CREATE INDEX ON notifications (tenant_id);
