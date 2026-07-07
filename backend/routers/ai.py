import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import (
    ASK_RATE_LIMIT,
    EMBED_MODEL,
    KB_MAX_CONTEXT_CHARS,
    KB_TOP_K,
    MISTRAL_MODEL,
    REQUEST_TIMEOUT,
    build_rag_prompt,
    get_current_user,
    get_user_by_email,
    is_admin_or_sav,
    limiter,
    rate_limit_key_by_user,
)
from mistral_client import embed_text, stream_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["IA"])


@router.post(
    "/ask/stream",
    summary="Interroger le modèle Mistral AI avec RAG",
    description=(
        "Envoie une question au modèle Mistral AI. "
        "La question est d'abord vectorisée (mistral-embed), puis les documents les plus proches "
        "sont récupérés depuis la base de connaissances (pgvector). "
        "Un prompt enrichi du contexte est envoyé au modèle Mistral, "
        "et la réponse est streamée token par token en `text/plain`."
    ),
)
@limiter.limit(ASK_RATE_LIMIT, key_func=rate_limit_key_by_user)
def ask_question_stream(request: Request, payload: schemas.AskRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    question, session_id, mode = payload.question, payload.session_id, payload.mode

    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id, models.ChatSession.deleted_at.is_(None)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if not is_admin_or_sav(user) and session.id_utilisateur != user.id:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if getattr(session, "status", "open") == "closed":
        raise HTTPException(status_code=400, detail="Cette conversation est clôturée.")

    db.add(models.ChatMessage(id_session=session_id, type_envoyeur="user", contenu=question))
    db.commit()

    if not session.title or session.title.strip().lower() == "nouvelle conversation":
        auto_title = question.strip().replace("\n", " ")
        if auto_title:
            session.title = auto_title[:80]
            db.commit()

    context = ""
    rag_chunks_found = 0
    rag_context_chars = 0
    try:
        query_embedding = embed_text(question, model=EMBED_MODEL, timeout=REQUEST_TIMEOUT)
        kb_rows = db.query(models.KnowledgeBase).order_by(models.KnowledgeBase.embedding.cosine_distance(query_embedding)).limit(KB_TOP_K).all()
        if kb_rows:
            context = "\n\n".join(r.contenu for r in kb_rows if r.contenu)[:KB_MAX_CONTEXT_CHARS]
            rag_chunks_found = len(kb_rows)
            rag_context_chars = len(context)
    except Exception as e:
        logger.warning("RAG context error: %s", e, exc_info=True)
        db.rollback()

    prompt = build_rag_prompt(question, context)

    if mode == "rag_only":
        ai_text = context or "Aucun contexte disponible."
        db.add(models.ChatMessage(id_session=session_id, type_envoyeur="ai", contenu=ai_text))
        db.commit()
        return StreamingResponse(iter([ai_text]), media_type="text/plain")

    def stream_tokens():
        t_start = time.perf_counter()
        success = True
        error_type = None
        ai_chunks: list[str] = []
        try:
            for token in stream_text(prompt, model=MISTRAL_MODEL, timeout=REQUEST_TIMEOUT):
                if token:
                    ai_chunks.append(token)
                    yield token
        except Exception as e:
            error_text = "Erreur IA pendant la génération."
            logger.error("Stream error: %s", e, exc_info=True)
            yield error_text
            ai_chunks.append(error_text)
            success = False
            error_type = type(e).__name__
        finally:
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            ai_text = "".join(ai_chunks).strip() or "Réponse IA invalide"
            db.add(models.ChatMessage(id_session=session_id, type_envoyeur="ai", contenu=ai_text))
            try:
                db.add(models.AICallLog(
                    id_session=session_id,
                    call_type="stream",
                    model_name=MISTRAL_MODEL,
                    latency_ms=latency_ms,
                    rag_chunks_found=rag_chunks_found,
                    rag_context_chars=rag_context_chars,
                    success=success,
                    error_type=error_type,
                ))
            except Exception:
                pass
            db.commit()

    return StreamingResponse(stream_tokens(), media_type="text/plain")
