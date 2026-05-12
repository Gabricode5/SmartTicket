# Modélisation des parcours utilisateurs

**Projet :** SmartTicket — Gestionnaire de tickets intelligent avec assistant virtuel  
**Acteurs :** Client (rôle `user`), Opérateur SAV (rôle `sav`), Administrateur (rôle `admin`)

---

## 1. Diagramme de cas d'usage UML

Représentation des use cases par acteur. Les relations `<<include>>` signalent les comportements obligatoires inclus.

```mermaid
flowchart LR
    Client(["Client"])
    Operateur(["Opérateur SAV"])
    Admin(["Administrateur"])

    subgraph SYS["Système SmartTicket"]
        UC5["Se connecter / S'authentifier"]

        subgraph GRP_CLIENT["Use Cases Client"]
            UC1["Poser une question au chatbot"]
            UC2["Recevoir une réponse RAG"]
            UC3["Demander transfert vers opérateur"]
            UC4["Suivre l'état d'un ticket"]
        end

        subgraph GRP_OP["Use Cases Opérateur SAV"]
            UC6["Consulter sessions transférées"]
            UC7["Répondre à un client"]
            UC8["Évaluer réponse du bot"]
            UC9["Résoudre une session"]
        end

        subgraph GRP_ADMIN["Use Cases Administrateur"]
            UC10["Ingérer un document"]
            UC11["Supprimer une source"]
            UC12["Consulter les métriques Analytics"]
            UC13["Gérer les utilisateurs"]
        end
    end

    Client --> UC5
    Client --> UC1
    Client --> UC3
    Client --> UC4
    UC1 -->|"include"| UC2

    Operateur --> UC5
    Operateur --> UC6
    Operateur --> UC7
    Operateur --> UC8
    Operateur --> UC9

    Admin --> UC5
    Admin --> UC10
    Admin --> UC11
    Admin --> UC12
    Admin --> UC13
    Admin --> UC6
    Admin --> UC8
```

---

## 2. Diagrammes de séquence

### 2.1 Parcours nominal — Client pose une question, le bot répond (RAG complet)

```mermaid
sequenceDiagram
    participant C as Client UI
    participant AG as API Gateway (FastAPI)
    participant Auth as Auth Service
    participant CS as Conversation Service
    participant ES as Embedding Service (Mistral)
    participant VDB as Vector DB (pgvector)
    participant LLM as LLM Service (Mistral)
    participant DB as PostgreSQL

    C->>AG: POST /api/ai/ask { question, session_id }
    AG->>Auth: Valider JWT (cookie httpOnly)
    Auth-->>AG: { user_id, role: "user" }
    AG->>CS: process_question(user_id, session_id, question)

    CS->>DB: INSERT message { type_envoyeur="user", contenu=question }
    DB-->>CS: message_id

    CS->>ES: embed_text(question)
    ES->>ES: Appel Mistral Embed API<br/>modèle: mistral-embed
    ES-->>CS: vector[1024]

    CS->>VDB: SELECT chunks ORDER BY (embedding <=> vector) LIMIT 4
    VDB-->>CS: chunks[] (top 4 par similarité cosinus)

    CS->>LLM: stream_text(rag_prompt + chunks + question)
    Note over CS,LLM: Prompt RAG construit côté serveur uniquement

    loop Token streaming (SSE)
        LLM-->>C: data: { token }
    end

    LLM-->>CS: réponse complète

    CS->>DB: INSERT message { type_envoyeur="ai", contenu=réponse_complète }
    DB-->>CS: message_id

    CS-->>C: SSE: [DONE]
    C->>C: Afficher réponse complète + boutons feedback
```

---

### 2.2 Parcours d'escalade — Client pose une question, transfert vers opérateur

```mermaid
sequenceDiagram
    participant C as Client UI
    participant AG as API Gateway (FastAPI)
    participant Auth as Auth Service
    participant CS as Conversation Service
    participant TS as Ticket Service
    participant NS as Notification Service
    participant DB as PostgreSQL
    participant Op as Opérateur SAV

    Note over C,Op: Scénario : le client demande explicitement un opérateur

    C->>AG: POST /api/sessions/{id}/transfer { motif: "complexe" }
    AG->>Auth: Valider JWT
    Auth-->>AG: { user_id, role: "user" }

    AG->>TS: transfer_session(session_id, user_id, motif)
    TS->>DB: Vérifier session appartient à user_id
    DB-->>TS: session { statut: "open" }

    TS->>DB: UPDATE ticket SET statut="transferred",<br/>motif_transfert="complexe"
    DB-->>TS: OK

    TS->>NS: notify_sav_team(session_id, motif, client_info)
    NS->>Op: Notification push / email<br/>"Nouvelle session transférée — motif : complexe"

    TS-->>AG: { status: "transferred", session_id }
    AG-->>C: 200 OK { message: "Transfert effectué" }

    C->>C: Afficher "En attente d'un opérateur..."
    Note over C: aria-live="assertive" annonce le changement de statut

    Op->>AG: GET /api/sessions?statut=transferred
    AG->>Auth: Valider JWT opérateur
    Auth-->>AG: { user_id, role: "sav" }
    AG->>DB: SELECT sessions WHERE statut="transferred" ORDER BY date_creation ASC
    DB-->>Op: Liste des sessions transférées

    Op->>AG: GET /api/sessions/{id}/messages
    AG->>DB: SELECT messages WHERE id_ticket={id}
    DB-->>Op: Historique complet (messages client + bot)

    Op->>AG: POST /api/messages { type_envoyeur="sav", contenu, session_id }
    AG->>DB: INSERT message
    DB-->>AG: OK
    AG-->>C: Notification temps réel (WebSocket / polling)
    C->>C: Afficher message de l'opérateur
```

---

### 2.3 Parcours d'ingestion — Admin ajoute un document (chunking + embedding + indexation)

```mermaid
sequenceDiagram
    participant A as Administrateur UI
    participant AG as API Gateway (FastAPI)
    participant Auth as Auth Service
    participant IS as Ingestion Service
    participant PS as Parser Service
    participant ES as Embedding Service (Mistral)
    participant VDB as Vector DB (pgvector)
    participant DB as PostgreSQL

    A->>AG: POST /api/knowledge/ingest { type: "file", fichier: doc.pdf }
    AG->>Auth: Valider JWT
    Auth-->>AG: { user_id, role: "admin" }

    AG->>IS: start_ingestion_job(fichier, type="pdf")
    IS->>DB: INSERT article { titre, source_url, id_categorie }
    DB-->>IS: article_id

    IS-->>AG: { job_id, status: "running" }
    AG-->>A: 202 Accepted { job_id }
    Note over A: Polling ou SSE pour suivre la progression

    IS->>PS: parse_document(fichier)
    Note over PS: pypdf → extraction texte brut
    PS-->>IS: contenu_texte_brut

    IS->>IS: chunk_text(contenu, chunk_size=500, overlap=50)
    Note over IS: N chunks produits

    loop Pour chaque chunk
        IS->>ES: embed_text(chunk.contenu)
        ES->>ES: Appel Mistral Embed API
        ES-->>IS: vector[1024]
        IS->>VDB: INSERT chunk { contenu, embedding, id_article }
        VDB-->>IS: chunk_id
        IS->>DB: UPDATE job progression
    end

    IS->>DB: UPDATE article SET statut="indexed"
    IS-->>AG: job terminé { chunks_created: N, status: "completed" }

    A->>AG: GET /api/knowledge/jobs/{job_id}
    AG-->>A: { status: "completed", chunks_created: N }
    A->>A: Afficher "Ingestion réussie : N chunks indexés"
```

---

## 3. Schémas fonctionnels des parcours utilisateurs principaux

### 3.1 Parcours Client — Du problème à la résolution

```mermaid
flowchart TD
    START(["Client rencontre un problème"]) --> AUTH{"Authentifié ?"}
    AUTH -->|Non| LOGIN["Page de connexion"]
    LOGIN --> AUTH
    AUTH -->|Oui| OPEN["Ouvrir le widget de chat"]

    OPEN --> SAISIE["Saisir la question en langage naturel"]
    SAISIE --> VALID{"Message valide ?\nlongueur > 0 et <= 2000 car."}
    VALID -->|Non| ERR_MSG["Afficher erreur de validation"]
    ERR_MSG --> SAISIE

    VALID -->|Oui| SEND["Envoyer la question\nPOST /api/ai/ask"]
    SEND --> LOADING["Indicateur de chargement\naria-live=polite"]

    LOADING --> RAG{"Pipeline RAG :\nchunks trouvés ?"}
    RAG -->|"Oui, >= 1 chunk"| LLM["Génération streaming\nMistral LLM"]
    RAG -->|"Non, score trop bas"| FALLBACK["Réponse générique\n+ suggestion escalade"]

    LLM --> STREAM["Affichage token par token\nSSE streaming"]
    STREAM --> SATISFIED{"Client satisfait ?"}
    FALLBACK --> SATISFIED

    SATISFIED -->|Oui| FEEDBACK_POS["Feedback positif\nFeedback = 1"]
    SATISFIED -->|Non| ESCALADE{"Demander un opérateur ?"}

    ESCALADE -->|Non| SAISIE
    ESCALADE -->|Oui| MOTIF["Sélectionner motif\ntechnique / complexe / sensible"]
    MOTIF --> TRANSFER["POST /api/sessions/:id/transfer"]
    TRANSFER --> ATTENTE["Statut: En attente d'un opérateur\naria-live=assertive"]
    ATTENTE --> OP_REPOND["Opérateur répond"]
    OP_REPOND --> RESOLVED["Session résolue\nstatut = resolved"]

    FEEDBACK_POS --> END(["Fin — problème résolu"])
    RESOLVED --> END
```

---

### 3.2 Parcours Opérateur SAV — Traitement d'une session transférée

```mermaid
flowchart TD
    START(["Opérateur reçoit une notification"]) --> LOGIN["Connexion rôle sav"]
    LOGIN --> DASHBOARD["Dashboard opérateur\nListe sessions transférées"]

    DASHBOARD --> SELECT["Sélectionner une session par ancienneté"]
    SELECT --> HISTORIQUE["Lire l'historique complet\nmessages client + bot"]

    HISTORIQUE --> ANALYSE{"Analyse de la situation"}
    ANALYSE -->|"Problème compréhensible"| REPONSE["Rédiger une réponse\ntype_envoyeur = sav"]
    ANALYSE -->|"Besoin info complémentaire"| QUESTION_CLIENT["Demander info au client"]
    QUESTION_CLIENT --> ATTENTE_CLIENT["Attendre réponse du client"]
    ATTENTE_CLIENT --> HISTORIQUE

    REPONSE --> SEND["POST /api/messages"]
    SEND --> FEEDBACK_BOT{"Évaluer réponses du bot ?"}
    FEEDBACK_BOT -->|Oui| RATE["Évaluer les messages bot\nPATCH /api/messages/:id/feedback"]
    RATE --> RESOLU{"Problème résolu ?"}
    FEEDBACK_BOT -->|Non| RESOLU

    RESOLU -->|Non| REPONSE
    RESOLU -->|Oui| CLOSE["Marquer résolu\nPATCH /api/sessions/:id\nstatut = resolved"]

    CLOSE --> NEXT["Session suivante dans la liste"]
    NEXT --> DASHBOARD
```

---

### 3.3 Parcours Administrateur — Maintenance et pilotage

```mermaid
flowchart TD
    START(["Administrateur se connecte"]) --> MENU{"Que veut faire l'admin ?"}

    MENU -->|"Gérer la base documentaire"| KB["Interface Knowledge Base"]
    MENU -->|"Consulter les métriques"| ANALYTICS["Page Analytics"]
    MENU -->|"Gérer les utilisateurs"| USERS["Interface Utilisateurs"]

    KB --> KB_ACTION{"Action"}
    KB_ACTION -->|Ajouter| INGEST_TYPE{"Type de source"}
    INGEST_TYPE -->|"URL / sitemap"| URL_FORM["Saisir URL\nVérification robots.txt"]
    INGEST_TYPE -->|"Fichier PDF/DOCX/TXT"| FILE_UPLOAD["Upload fichier\nMax 50 Mo"]

    URL_FORM --> INGEST_JOB["POST /api/knowledge/ingest\nJob arrière-plan"]
    FILE_UPLOAD --> INGEST_JOB

    INGEST_JOB --> JOB_STATUS{"Statut job"}
    JOB_STATUS -->|"En cours"| PROGRESS["Barre de progression\nN chunks / total estimé"]
    PROGRESS --> JOB_STATUS
    JOB_STATUS -->|Succès| SUCCESS["N chunks indexés\nnotification succès"]
    JOB_STATUS -->|Erreur| ERR["Message d'erreur détaillé\naria-describedby"]
    ERR --> KB_ACTION

    KB_ACTION -->|Supprimer| CONFIRM_DEL["Modale de confirmation\nSupprimer cette source et N chunks associés ?"]
    CONFIRM_DEL -->|Confirmer| DELETE["DELETE /api/knowledge/:id\nCascade sur chunks"]
    DELETE --> KB

    ANALYTICS --> KPI["Afficher KPIs\nTaux résolution IA\nScore satisfaction\nNb transferts par motif"]
    KPI --> FILTER["Filtrer par période\n7j / 30j / 90j"]
    FILTER --> CHARTS["Graphiques Recharts\navec alternatives textuelles"]
    CHARTS --> ALERT{"Alerte détectée ?"}
    ALERT -->|Oui| DRILL["Cliquer pour voir sessions détaillées"]
    ALERT -->|Non| MENU

    USERS --> USER_LIST["Liste des utilisateurs\navec rôle et date"]
    USER_LIST --> USER_ACTION{"Action"}
    USER_ACTION -->|"Changer rôle"| ROLE_UPDATE["PATCH /api/users/:id/role"]
    USER_ACTION -->|"Supprimer utilisateur"| USER_DEL["DELETE /api/users/:id\nCascade RGPD"]
    ROLE_UPDATE --> USER_LIST
    USER_DEL --> USER_LIST
```
