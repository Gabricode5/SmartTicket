from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import get_current_user, get_user_by_email, is_admin_or_sav

router = APIRouter(tags=["Messages"])


@router.get("/messages", response_model=list[schemas.ChatMessageResponse], summary="Lister les messages d'une session")
def list_messages(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if not is_admin_or_sav(user) and session.id_utilisateur != user.id:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    return db.query(models.ChatMessage).filter(models.ChatMessage.id_session == session_id).order_by(models.ChatMessage.date_creation.asc()).all()


@router.post("/messages", response_model=schemas.ChatMessageResponse, status_code=status.HTTP_201_CREATED, summary="Envoyer un message dans une session")
def create_message(message: schemas.ChatMessageCreate, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == message.id_session).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if not is_admin_or_sav(user) and session.id_utilisateur != user.id:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if getattr(session, "status", "open") == "closed":
        raise HTTPException(status_code=400, detail="Cette conversation est clôturée.")
    if message.type_envoyeur not in ["user", "ai", "sav"]:
        raise HTTPException(status_code=400, detail="Type d'envoyeur invalide")
    new_message = models.ChatMessage(id_session=message.id_session, type_envoyeur=message.type_envoyeur, contenu=message.contenu)
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message


@router.patch("/messages/{message_id}/feedback", summary="Noter une réponse IA (pouce haut/bas)")
def rate_message(message_id: int, payload: schemas.MessageFeedbackRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.feedback not in (1, -1):
        raise HTTPException(status_code=400, detail="feedback doit être 1 ou -1")
    message = db.query(models.ChatMessage).filter(models.ChatMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message introuvable")
    if message.type_envoyeur != "ai":
        raise HTTPException(status_code=400, detail="Le feedback n'est applicable qu'aux messages IA")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == message.id_session).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if not is_admin_or_sav(user) and session.id_utilisateur != user.id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    message.feedback = payload.feedback
    db.commit()
    return {"ok": True}
