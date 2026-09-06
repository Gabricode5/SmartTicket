"""Retrieval : question -> contexte RAG.

Portage de la "recette" de backend/routers/ai.py, sortie de tout contexte FastAPI/auth :
  1. embed(question)
  2. SELECT ... ORDER BY embedding <=> :q LIMIT KB_TOP_K * RERANK_FETCH_MULTIPLIER
  3. rerank_chunks(...) avec le feedback porte par chaque chunk
  4. concatenation des top-k, tronquee a KB_MAX_CONTEXT_CHARS

best_match_distance est capturee AVANT reranking (comme cote Tiqia) : c'est une mesure de
pertinence pure du retrieval, que le reranking (feedback + lexical) fausserait.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from rag_core.config import KB_MAX_CONTEXT_CHARS, KB_TOP_K, RERANK_FETCH_MULTIPLIER
from rag_core.llm.factory import get_embedder
from rag_core.models import KnowledgeChunk
from rag_core.reranking import rerank_chunks


@dataclass
class RetrievedContext:
    context: str
    chunk_ids: list[int]
    best_match_distance: float | None
    chunk_count: int


def retrieve(db: Session, question: str, *, embedder=None) -> RetrievedContext:
    """Retourne le contexte RAG pour `question`. `embedder` injectable pour les tests."""
    embedder = embedder or get_embedder()
    query_embedding = embedder.embed_one(question)

    rows = (
        db.query(
            KnowledgeChunk,
            KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .order_by("distance")
        .limit(KB_TOP_K * RERANK_FETCH_MULTIPLIER)
        .all()
    )
    if not rows:
        return RetrievedContext(context="", chunk_ids=[], best_match_distance=None, chunk_count=0)

    candidates = [row[0] for row in rows]
    best_match_distance = float(rows[0][1])
    feedback_by_id = {c.id: (c.feedback_score or 0) for c in candidates}

    ranked = rerank_chunks(question, candidates, feedback_by_id, KB_TOP_K)
    context = "\n\n".join(c.contenu for c in ranked if c.contenu)[:KB_MAX_CONTEXT_CHARS]
    return RetrievedContext(
        context=context,
        chunk_ids=[c.id for c in ranked],
        best_match_distance=best_match_distance,
        chunk_count=len(ranked),
    )
