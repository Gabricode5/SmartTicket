"""Reranking des chunks RAG et ajustement du seuil de qualité selon le feedback.

Le retrieval pgvector (ORDER BY cosine_distance) donne un premier classement par
similarité sémantique. Ce module affine ce classement en combinant trois signaux :
  1. le rang de similarité vectorielle (signal dominant),
  2. le recouvrement lexical entre la question et le contenu du chunk,
  3. le feedback utilisateur accumulé sur ce chunk (via chat_messages.source_kb_ids).

Un chunk dont le feedback net devient trop négatif est mis en quarantaine : il est
exclu du contexte quelle que soit sa similarité vectorielle.
"""
import os
import re
from typing import Protocol

RERANK_FETCH_MULTIPLIER = int(os.getenv("RERANK_FETCH_MULTIPLIER", "3"))
RERANK_LEXICAL_WEIGHT = float(os.getenv("RERANK_LEXICAL_WEIGHT", "0.3"))
RERANK_FEEDBACK_WEIGHT = float(os.getenv("RERANK_FEEDBACK_WEIGHT", "0.2"))
RERANK_QUARANTINE_THRESHOLD = int(os.getenv("RERANK_QUARANTINE_THRESHOLD", "-3"))

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_MIN_TOKEN_LEN = 3


class _Chunk(Protocol):
    id: int
    contenu: str | None


def _tokenize(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) >= _MIN_TOKEN_LEN}


def _lexical_overlap(question_tokens: set[str], content: str | None) -> float:
    """Part du vocabulaire de la question retrouvée dans le contenu du chunk (0.0-1.0)."""
    if not question_tokens or not content:
        return 0.0
    content_tokens = _tokenize(content)
    if not content_tokens:
        return 0.0
    return len(question_tokens & content_tokens) / len(question_tokens)


def rerank_chunks(
    question: str,
    candidates: list[_Chunk],
    feedback_by_kb_id: dict[int, int],
    top_k: int,
) -> list[_Chunk]:
    """Reclasse des candidats déjà triés par similarité cosinus (ordre = `candidates`,
    du plus au moins similaire) et retourne les `top_k` meilleurs après reranking.

    `feedback_by_kb_id` : somme des feedback (1/-1) des messages IA ayant utilisé
    chaque chunk, tel que retourné par une agrégation sur chat_messages.source_kb_ids.
    """
    if not candidates:
        return []

    question_tokens = _tokenize(question)
    total = len(candidates)
    scored: list[tuple[float, _Chunk]] = []

    for rank, chunk in enumerate(candidates):
        net_feedback = feedback_by_kb_id.get(chunk.id, 0)
        if net_feedback <= RERANK_QUARANTINE_THRESHOLD:
            continue  # quarantaine : feedback négatif répété, on n'y touche plus

        similarity_score = 1.0 - (rank / total) if total > 1 else 1.0
        lexical_score = _lexical_overlap(question_tokens, chunk.contenu)
        feedback_score = max(-1.0, min(1.0, net_feedback / 5))

        composite = similarity_score + RERANK_LEXICAL_WEIGHT * lexical_score + RERANK_FEEDBACK_WEIGHT * feedback_score
        scored.append((composite, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]
