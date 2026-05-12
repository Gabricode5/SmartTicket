from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import (
    EMBED_MODEL, MISTRAL_MODEL, REQUEST_TIMEOUT,
    SUMMARY_MAX_CHARS, SUMMARY_MAX_MESSAGES,
    TRANSCRIPT_CHUNK_OVERLAP, TRANSCRIPT_CHUNK_SIZE, TRANSCRIPT_MAX_CHARS,
    chunk_text, get_current_user, get_user_by_email, is_admin_or_sav, sanitize_text,
)
from mistral_client import embed_text, generate_text

router = APIRouter(tags=["Sessions"])

VALID_REASONS = {"technique", "complexe", "sensible", "autre"}
REASON_LABELS = {"technique": "Technique", "complexe": "Complexe", "sensible": "Sensible", "autre": "Autre"}
REASON_COLORS = {"technique": "#0ea5e9", "complexe": "#f59e0b", "sensible": "#ef4444", "autre": "#8b5cf6"}


@router.post("/sessions", response_model=schemas.ChatSessionResponse, summary="Créer une session de chat")
def create_session(session_data: schemas.ChatSessionCreate, user_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and requester.id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    new_session = models.ChatSession(id_utilisateur=user_id, title=session_data.title)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@router.get("/sessions", response_model=list[schemas.ChatSessionResponse], summary="Lister les sessions d'un utilisateur")
def list_sessions(user_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and requester.id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return db.query(models.ChatSession).filter(models.ChatSession.id_utilisateur == user_id).order_by(models.ChatSession.date_creation.desc()).all()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une session")
def delete_session(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and session.id_utilisateur != requester.id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    db.query(models.ChatMessage).filter(models.ChatMessage.id_session == session_id).delete(synchronize_session=False)
    db.delete(session)
    db.commit()


@router.post("/sessions/{session_id}/close", response_model=schemas.ChatSessionResponse, summary="Clôturer une session (génère un résumé IA et indexe le transcript)")
def close_session(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and session.id_utilisateur != requester.id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if getattr(session, "status", "open") == "closed":
        return session

    messages = db.query(models.ChatMessage).filter(models.ChatMessage.id_session == session_id).order_by(models.ChatMessage.date_creation.asc()).limit(SUMMARY_MAX_MESSAGES).all()
    transcript_parts = [sanitize_text(f"{m.type_envoyeur.upper()}: {m.contenu}") for m in messages if m.contenu]
    transcript = "\n".join(transcript_parts)[:TRANSCRIPT_MAX_CHARS]

    if not transcript:
        summary_text = "Ticket clos sans message."
    else:
        summary_prompt = f"Tu es un agent SAV. Résume ce ticket en 5 à 8 lignes maximum.\nInclue: problème principal, actions tentées, solution finale (si connue).\n\nTRANSCRIPT:\n{transcript[:SUMMARY_MAX_CHARS]}"
        summary_text = ""
        try:
            summary_text = sanitize_text(generate_text(summary_prompt, model=MISTRAL_MODEL, timeout=REQUEST_TIMEOUT))
        except Exception:
            pass
        if not summary_text:
            first = transcript_parts[0] if transcript_parts else ""
            last = transcript_parts[-1] if transcript_parts else ""
            summary_text = sanitize_text("Résumé court du ticket:\n" + "\n".join(p for p in [first, last] if p))

    try:
        summary_embedding = embed_text(sanitize_text(summary_text), model=EMBED_MODEL, timeout=REQUEST_TIMEOUT)
        db.add(models.KnowledgeBase(source_message_id=None, contenu=f"Résumé session #{session_id} (user_id={session.id_utilisateur})\n{summary_text}", embedding=summary_embedding, category="ticket_summary"))
    except Exception:
        pass

    if transcript:
        try:
            chunks = chunk_text(transcript, TRANSCRIPT_CHUNK_SIZE, TRANSCRIPT_CHUNK_OVERLAP)
            for idx, chunk in enumerate(chunks, start=1):
                chunk = sanitize_text(chunk)
                if not chunk:
                    continue
                vector = embed_text(chunk, model=EMBED_MODEL, timeout=REQUEST_TIMEOUT)
                db.add(models.KnowledgeBase(source_message_id=None, contenu=f"Transcript session #{session_id} (user_id={session.id_utilisateur}) [{idx}/{len(chunks)}]\n{chunk}", embedding=vector, category="ticket_transcript"))
        except Exception:
            pass

    session.status = "closed"
    db.commit()
    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/transfer", response_model=schemas.ChatSessionResponse, summary="Transférer la session vers un agent humain")
def transfer_session(session_id: int, payload: schemas.TransferRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.reason not in VALID_REASONS:
        raise HTTPException(status_code=400, detail=f"Raison invalide. Valeurs acceptées : {', '.join(VALID_REASONS)}")
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    if session.id_utilisateur != user.id and not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    if session.status != "open":
        raise HTTPException(status_code=400, detail="Cette session ne peut pas être transférée.")
    session.status = "transferred"
    session.transfer_reason = payload.reason
    db.add(models.ChatMessage(id_session=session_id, type_envoyeur="ai", contenu=f"Vous avez été mis en relation avec un agent humain. Raison : {REASON_LABELS.get(payload.reason, payload.reason)}."))
    db.commit()
    db.refresh(session)
    return {"id": session.id, "id_utilisateur": session.id_utilisateur, "title": session.title, "status": session.status, "transfer_reason": session.transfer_reason, "date_creation": session.date_creation}


@router.post("/sessions/{session_id}/resolve", response_model=schemas.ChatSessionResponse, summary="Rétablir l'IA après un transfert humain")
def resolve_session(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    if session.status != "transferred":
        raise HTTPException(status_code=400, detail="Cette session n'est pas en transfert.")
    session.status = "open"
    session.transfer_reason = None
    db.add(models.ChatMessage(id_session=session_id, type_envoyeur="ai", contenu="L'agent SAV a rétabli la conversation avec l'assistant IA."))
    db.commit()
    db.refresh(session)
    return {"id": session.id, "id_utilisateur": session.id_utilisateur, "title": session.title, "status": session.status, "transfer_reason": session.transfer_reason, "date_creation": session.date_creation}


@router.get("/sessions/transferred", summary="Lister les sessions en attente d'un agent humain")
def get_transferred_sessions(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    rows = db.query(models.ChatSession, models.Utilisateur.username).join(models.Utilisateur, models.ChatSession.id_utilisateur == models.Utilisateur.id).filter(models.ChatSession.status == "transferred").order_by(models.ChatSession.date_creation.desc()).all()
    return [{"id": s.id, "title": s.title, "status": s.status, "transfer_reason": s.transfer_reason, "date_creation": s.date_creation, "username": username} for s, username in rows]
