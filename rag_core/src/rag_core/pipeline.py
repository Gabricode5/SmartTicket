"""Point d'entree public de rag_core : answer(db, question) -> AnswerResult.

Assemble retrieval + prompt a deux couches + generation. Non streame : produit une
suggestion complete destinee a un agent humain.

La passerelle est responsable, en aval, de :
  - prefixer "[Suggestion IA - a valider]",
  - apposer la mention AI Act (rag_core.prompt.AI_ASSISTANCE_DISCLOSURE_FR) si la reponse
    part vers le client final,
  - decider quoi faire de low_confidence (ne pas suggerer, suggerer avec avertissement...).
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from rag_core.config import RAG_LOW_CONFIDENCE_DISTANCE
from rag_core.llm.factory import get_embedder, get_generator
from rag_core.prompt import build_prompt
from rag_core.retriever import retrieve


@dataclass
class AnswerResult:
    suggestion: str
    chunk_ids: list[int]
    best_match_distance: float | None
    chunk_count: int
    #: True si aucun chunk, ou si le meilleur chunk depasse RAG_LOW_CONFIDENCE_DISTANCE.
    low_confidence: bool
    #: modele de generation effectivement utilise (nom catalogue).
    model: str


def answer(
    db: Session,
    question: str,
    *,
    client_overlay: str | None = None,
    embedder=None,
    generator=None,
) -> AnswerResult:
    """embedder / generator injectables pour les tests (sinon resolus via le catalogue)."""
    embedder = embedder or get_embedder()
    generator = generator or get_generator()

    ctx = retrieve(db, question, embedder=embedder)
    prompt = build_prompt(question, ctx.context, client_overlay=client_overlay)
    suggestion = generator.generate(prompt).strip()

    low_confidence = (
        ctx.best_match_distance is None
        or ctx.best_match_distance > RAG_LOW_CONFIDENCE_DISTANCE
    )
    return AnswerResult(
        suggestion=suggestion,
        chunk_ids=ctx.chunk_ids,
        best_match_distance=ctx.best_match_distance,
        chunk_count=ctx.chunk_count,
        low_confidence=low_confidence,
        model=generator.model,
    )
