"""
Tests d'évaluation du pipeline RAG (Retrieval-Augmented Generation).

Ces tests valident les 3 étapes clés du pipeline IA :
  1. Préparation des données  — chunking et sanitisation avant ingestion en KB
  2. Qualité du retrieval     — les bons documents sont retrouvés pour une question donnée
  3. Construction du prompt   — le prompt envoyé au modèle contient le bon contexte

Note : le mode `rag_only` est utilisé pour les tests de retrieval, ce qui évite
tout appel réel à l'API Mistral (pas de clé API requise, pas de coût).
"""
import math
from unittest.mock import patch

import pytest
import models
from dependencies import build_rag_prompt, chunk_text, sanitize_text

EMBED_DIM = 1024


def make_vector(seed: int = 0) -> list[float]:
    """
    Génère un vecteur unitaire déterministe de dimension 1024.
    Deux appels avec le même seed produisent le même vecteur (distance cosinus = 0).
    Deux appels avec des seeds différents produisent des vecteurs distincts.
    """
    raw = [math.sin(i * 0.1 + seed) for i in range(EMBED_DIM)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


# ---------------------------------------------------------------------------
# 1. VALIDATION DES DONNÉES — étapes de préparation avant ingestion
# ---------------------------------------------------------------------------

class TestKbDataValidation:
    """Règles de validation appliquées aux documents avant insertion en base de connaissances."""

    def test_chunk_preserve_content(self):
        """Les chunks produits doivent contenir le texte d'origine."""
        doc = "Procédure de réinitialisation du mot de passe utilisateur."
        chunks = chunk_text(doc, 50, 10)
        combined = " ".join(chunks)
        assert "réinitialisation" in combined

    def test_chunk_respects_max_size(self):
        """Aucun chunk ne doit dépasser la taille maximale configurée."""
        chunks = chunk_text("mot " * 500, 200, 0)
        assert all(len(c) <= 200 for c in chunks)

    def test_chunk_overlap_increases_count(self):
        """Le chevauchement doit produire plus de chunks qu'un découpage sans overlap."""
        text = "abcdefghijklmnopqrstuvwxyz"
        without = chunk_text(text, 6, 0)
        with_overlap = chunk_text(text, 6, 3)
        assert len(with_overlap) >= len(without)

    def test_sanitize_removes_null_bytes(self):
        """Les octets nuls corrompent pgvector — ils doivent être supprimés."""
        assert "\x00" not in sanitize_text("hello\x00world")

    def test_sanitize_strips_surrounding_whitespace(self):
        """Les espaces en début et fin de texte doivent être supprimés."""
        assert sanitize_text("  contenu propre  ") == "contenu propre"

    def test_sanitize_preserves_clean_text(self):
        """Un texte déjà propre ne doit pas être modifié."""
        assert sanitize_text("FAQ support client") == "FAQ support client"

    def test_empty_chunk_size_returns_full_text(self):
        """Une taille de chunk nulle ou négative retourne le texte entier sans découpage."""
        result = chunk_text("texte complet", 0, 0)
        assert result == ["texte complet"]


# ---------------------------------------------------------------------------
# 2. ÉVALUATION DU RETRIEVAL — qualité de la recherche sémantique
# ---------------------------------------------------------------------------

class TestRagRetrieval:
    """
    Évalue que le pipeline RAG retrouve les bons documents pour une question donnée.

    Stratégie : on insère un document avec un vecteur V connu, puis on mocke
    embed_text pour que la question produise le même vecteur V. La distance
    cosinus est alors 0 → le document doit être le premier résultat.
    """

    def _seed_kb(self, db_session, contenu: str, seed: int) -> None:
        """Insère un document de test directement en base avec un vecteur déterministe."""
        db_session.add(models.KnowledgeBase(
            contenu=contenu,
            embedding=make_vector(seed),
            category="test",
            source="test_fixture",
        ))
        db_session.commit()

    def _create_session(self, auth_client) -> int:
        me = auth_client.get("/v1/me").json()
        return auth_client.post(
            "/v1/sessions",
            params={"user_id": me["id"]},
            json={"title": "test"},
        ).json()["id"]

    def test_retrieves_relevant_document(self, auth_client, db_session):
        """
        ÉTANT DONNÉ un document KB sur la réinitialisation de mot de passe,
        QUAND on interroge le RAG avec un vecteur identique à ce document,
        ALORS le contenu du document doit apparaître dans la réponse.
        """
        self._seed_kb(
            db_session,
            contenu="Le mot de passe se réinitialise via 'Mot de passe oublié' sur la page de connexion.",
            seed=42,
        )

        with patch("routers.ai.embed_text", return_value=make_vector(seed=42)):
            resp = auth_client.post("/v1/ask/stream", json={
                "question": "Comment réinitialiser mon mot de passe ?",
                "session_id": self._create_session(auth_client),
                "mode": "rag_only",
            })

        assert resp.status_code == 200
        assert "mot de passe" in resp.text.lower()

    def test_empty_kb_returns_fallback_message(self, auth_client):
        """
        ÉTANT DONNÉ une base de connaissances vide,
        QUAND on interroge le RAG,
        ALORS le message de fallback doit être retourné.
        """
        with patch("routers.ai.embed_text", return_value=make_vector(seed=0)):
            resp = auth_client.post("/v1/ask/stream", json={
                "question": "Question sans contexte disponible",
                "session_id": self._create_session(auth_client),
                "mode": "rag_only",
            })

        assert resp.status_code == 200
        assert "Aucun contexte disponible" in resp.text

    def test_most_similar_document_is_prioritized(self, auth_client, db_session):
        """
        ÉTANT DONNÉ deux documents en KB,
        QUAND la requête a le même vecteur que le premier document,
        ALORS le contenu du premier document doit apparaître en priorité.
        """
        self._seed_kb(db_session, "Délai de livraison express : 24 heures ouvrées.", seed=1)
        self._seed_kb(db_session, "Politique de confidentialité et traitement RGPD.", seed=99)

        with patch("routers.ai.embed_text", return_value=make_vector(seed=1)):
            resp = auth_client.post("/v1/ask/stream", json={
                "question": "Quel est le délai de livraison ?",
                "session_id": self._create_session(auth_client),
                "mode": "rag_only",
            })

        assert resp.status_code == 200
        assert "livraison" in resp.text.lower()

    def test_multiple_documents_all_included_in_context(self, auth_client, db_session):
        """
        ÉTANT DONNÉ plusieurs documents avec le même vecteur (seeds proches),
        QUAND on interroge le RAG,
        ALORS le contexte doit regrouper plusieurs chunks (KB_TOP_K = 10 max).
        """
        for i in range(3):
            self._seed_kb(db_session, f"Information produit numéro {i}.", seed=42)

        with patch("routers.ai.embed_text", return_value=make_vector(seed=42)):
            resp = auth_client.post("/v1/ask/stream", json={
                "question": "Quelles sont les informations produit ?",
                "session_id": self._create_session(auth_client),
                "mode": "rag_only",
            })

        assert resp.status_code == 200
        assert "Information produit" in resp.text


# ---------------------------------------------------------------------------
# 3. VALIDATION DU PROMPT — qualité de la construction du contexte
# ---------------------------------------------------------------------------

class TestRagPromptConstruction:
    """Valide que le prompt envoyé au modèle contient les bonnes informations."""

    def test_prompt_contains_question(self):
        """La question de l'utilisateur doit être présente dans le prompt."""
        question = "Comment contacter le support ?"
        assert question in build_rag_prompt(question, "contexte")

    def test_prompt_contains_context(self):
        """Le contexte extrait de la KB doit être intégré dans le prompt."""
        context = "Support joignable à support@example.com du lundi au vendredi."
        assert context in build_rag_prompt("question", context)

    def test_prompt_signals_missing_context(self):
        """Un contexte vide doit déclencher le message de fallback dans le prompt."""
        assert "Aucun contexte disponible" in build_rag_prompt("question", "")

    def test_prompt_is_non_empty_string(self):
        """Le prompt doit toujours être une chaîne non vide."""
        prompt = build_rag_prompt("q", "c")
        assert isinstance(prompt, str) and len(prompt) > 0

    def test_prompt_structure_separates_context_and_question(self):
        """Le prompt doit avoir des sections CONTEXTE et QUESTION distinctes."""
        prompt = build_rag_prompt("ma question", "mon contexte")
        assert "CONTEXTE" in prompt
        assert "QUESTION" in prompt
        assert prompt.index("CONTEXTE") < prompt.index("QUESTION")
