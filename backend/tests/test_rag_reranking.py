"""Tests unitaires purs du reranking RAG (aucune base de données requise)."""
from types import SimpleNamespace

import rag_reranking
from rag_reranking import rerank_chunks


def chunk(id: int, contenu: str) -> SimpleNamespace:
    return SimpleNamespace(id=id, contenu=contenu)


class TestRerankChunks:
    def test_empty_candidates_returns_empty(self):
        assert rerank_chunks("question", [], {}, top_k=5) == []

    def test_preserves_similarity_order_with_no_other_signal(self):
        """Sans feedback ni recouvrement lexical, l'ordre de similarité (ordre d'entrée) doit être conservé."""
        candidates = [chunk(1, "xyz abc"), chunk(2, "xyz abc"), chunk(3, "xyz abc")]
        result = rerank_chunks("question sans rapport", candidates, {}, top_k=3)
        assert [c.id for c in result] == [1, 2, 3]

    def test_respects_top_k(self):
        candidates = [chunk(i, "contenu générique") for i in range(10)]
        result = rerank_chunks("question", candidates, {}, top_k=3)
        assert len(result) == 3

    def test_lexical_overlap_can_promote_a_close_lower_ranked_chunk(self):
        """Sur un pool de candidats sur-échantillonné (comme en production, où l'écart
        de similarité entre rangs voisins est faible), un chunk légèrement moins bien
        classé mais très pertinent lexicalement doit remonter devant son voisin hors-sujet.
        La similarité reste dominante : un écart de rang trop grand ne serait pas comblé
        par le seul recouvrement lexical (poids volontairement modéré, 0.3)."""
        candidates = [chunk(0, "Contenu générique sans rapport, numéro zéro.")]
        candidates.append(chunk(1, "Procédure de réinitialisation du mot de passe utilisateur."))
        candidates += [chunk(i, f"Contenu générique sans rapport, numéro {i}.") for i in range(2, 20)]

        result = rerank_chunks("Comment réinitialiser mon mot de passe ?", candidates, {}, top_k=20)
        assert result[0].id == 1

    def test_quarantines_chunk_with_very_negative_feedback(self):
        """Un chunk au feedback net très négatif est exclu même s'il est le plus similaire."""
        candidates = [chunk(1, "meilleur match"), chunk(2, "second match")]
        feedback = {1: rag_reranking.RERANK_QUARANTINE_THRESHOLD}
        result = rerank_chunks("question", candidates, feedback, top_k=2)
        assert [c.id for c in result] == [2]

    def test_does_not_quarantine_mildly_negative_feedback(self):
        """Un feedback légèrement négatif (au-dessus du seuil) ne doit pas exclure le chunk."""
        candidates = [chunk(1, "contenu")]
        feedback = {1: rag_reranking.RERANK_QUARANTINE_THRESHOLD + 1}
        result = rerank_chunks("question", candidates, feedback, top_k=1)
        assert [c.id for c in result] == [1]

    def test_positive_feedback_breaks_ties_in_favor_of_liked_chunk(self):
        """À rangs voisins (écart de similarité faible, comme sur un pool sur-échantillonné)
        et pertinence lexicale égale, le chunk le mieux noté doit passer devant."""
        candidates = [chunk(1, "contenu identique"), chunk(2, "contenu identique")]
        candidates += [chunk(i, f"autre contenu numéro {i}") for i in range(3, 20)]
        feedback = {2: 5}
        result = rerank_chunks("question sans lien lexical", candidates, feedback, top_k=20)
        assert result[0].id == 2

    def test_handles_none_contenu_without_crashing(self):
        candidates = [chunk(1, None)]
        result = rerank_chunks("question", candidates, {}, top_k=1)
        assert [c.id for c in result] == [1]

    def test_single_candidate_gets_full_similarity_score(self):
        """Avec un seul candidat, la division par (total - 1) ne doit pas planter."""
        candidates = [chunk(1, "seul chunk disponible")]
        result = rerank_chunks("question", candidates, {}, top_k=5)
        assert [c.id for c in result] == [1]
