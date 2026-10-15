"""Reranking des chunks RAG -- portage de backend/rag_reranking.py (comportement identique).

Le retrieval pgvector (ORDER BY cosine_distance) donne un premier classement par
similarite semantique. Ce module l'affine en combinant trois signaux :
  1. le rang de similarite vectorielle (signal dominant),
  2. le recouvrement lexical entre la question et le contenu du chunk,
  3. le feedback accumule sur ce chunk (KnowledgeChunk.feedback_score).

Un chunk dont le feedback net atteint RERANK_QUARANTINE_THRESHOLD ou moins est exclu du
contexte quelle que soit sa similarite.
"""
import re
from typing import Protocol

from rag_core.config import (
    RERANK_FEEDBACK_WEIGHT,
    RERANK_LEXICAL_WEIGHT,
    RERANK_QUARANTINE_THRESHOLD,
)

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_MIN_TOKEN_LEN = 3


class _Chunk(Protocol):
    id: int
    contenu: str | None


def _tokenize(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) >= _MIN_TOKEN_LEN}


def _lexical_overlap(question_tokens: set[str], content: str | None) -> float:
    """Part du vocabulaire de la question retrouvee dans le contenu du chunk (0.0-1.0)."""
    if not question_tokens or not content:
        return 0.0
    content_tokens = _tokenize(content)
    if not content_tokens:
        return 0.0
    return len(question_tokens & content_tokens) / len(question_tokens)


def rerank_chunks(
    question: str,
    candidates: list[_Chunk],
    feedback_by_id: dict[int, int],
    top_k: int,
) -> list[_Chunk]:
    """Reclasse des candidats deja tries par similarite cosinus (ordre = `candidates`, du
    plus au moins similaire) et retourne les `top_k` meilleurs apres reranking.

    `feedback_by_id` : feedback net (somme des +1 / -1) par id de chunk.
    """
    if not candidates:
        return []

    question_tokens = _tokenize(question)
    total = len(candidates)
    scored: list[tuple[float, _Chunk]] = []

    for rank, chunk in enumerate(candidates):
        net_feedback = feedback_by_id.get(chunk.id, 0)
        if net_feedback <= RERANK_QUARANTINE_THRESHOLD:
            continue  # quarantaine : feedback negatif repete, on n'y touche plus

        similarity_score = 1.0 - (rank / total) if total > 1 else 1.0
        lexical_score = _lexical_overlap(question_tokens, chunk.contenu)
        feedback_score = max(-1.0, min(1.0, net_feedback / 5))

        composite = (
            similarity_score
            + RERANK_LEXICAL_WEIGHT * lexical_score
            + RERANK_FEEDBACK_WEIGHT * feedback_score
        )
        scored.append((composite, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]
