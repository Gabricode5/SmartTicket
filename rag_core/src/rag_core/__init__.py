"""rag_core -- bibliotheque RAG autonome.

Extraite par DUPLICATION du pipeline RAG de l'app Tiqia (backend/), pas par extraction
destructive : le backend garde son propre code RAG inchange. rag_core n'importe RIEN de
backend/ et vise une base pgvector dediee (RAG_DATABASE_URL), jamais celle de Tiqia.

Point d'entree principal : rag_core.pipeline.answer(db, question) -> AnswerResult.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
