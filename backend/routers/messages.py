from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import get_current_user, get_user_by_email, is_admin_or_sav
from notifications import queue_sav_reply, send_sav_reply_email

router = APIRouter(tags=["Messages"])


@router.get("/messages", response_model=list[schemas.ChatMessageResponse], summary="Lister les messages d'une session")
def list_messages(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id, models.ChatSession.deleted_at.is_(None)).first()
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
    session = db.query(models.ChatSession).filter(models.ChatSession.id == message.id_session, models.ChatSession.deleted_at.is_(None)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if not is_admin_or_sav(user) and session.id_utilisateur != user.id:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if getattr(session, "status", "open") == "closed":
        raise HTTPException(status_code=400, detail="Cette conversation est clôturée.")
    if message.type_envoyeur not in ["user", "ai", "sav"]:
        raise HTTPException(status_code=400, detail="Type d'envoyeur invalide")

    # Réutilise l'envoi de message existant plutôt qu'un endpoint "répondre au ticket" séparé
    # (décision Étape 2, 2026-08-18). Le ticket "courant" du cycle en cours est le plus récent
    # non-closed sur cette session (une session transférée plusieurs fois a plusieurs tickets,
    # cf. models.Ticket) ; aucun ticket trouvé = session pas (encore) passée par /transfer.
    current_ticket = None
    if message.type_envoyeur == "sav":
        current_ticket = db.query(models.Ticket).filter(
            models.Ticket.session_id == session.id,
            models.Ticket.status != "closed",
            models.Ticket.deleted_at.is_(None),
        ).order_by(models.Ticket.created_at.desc()).first()
        # Cloisonnement strict (même règle que _get_visible_ticket_or_404 dans
        # routers/tickets.py) : un agent sav (pas superviseur/admin) ne peut pas répondre sur
        # le ticket d'un collègue -- sans ce garde-fou ici, POST /messages contournait
        # entièrement le cloisonnement appliqué à GET/PATCH /tickets/{id} (bug trouvé le
        # 2026-08-17 en vérifiant cette hypothèse plutôt qu'en la supposant vraie). 404, pas
        # 403 : ne révèle même pas l'existence du ticket à un agent qui n'y a pas accès.
        if (
            current_ticket and user.role.nom_role == "sav"
            and current_ticket.assigned_agent_id is not None
            and current_ticket.assigned_agent_id != user.id
        ):
            raise HTTPException(status_code=404, detail="Session non trouvée")

    new_message = models.ChatMessage(id_session=message.id_session, type_envoyeur=message.type_envoyeur, contenu=message.contenu)
    db.add(new_message)
    if message.type_envoyeur == "sav":
        queue_sav_reply(db, session)
        if current_ticket:
            current_ticket.waiting_on = "customer"
            # Répondre à un ticket libre = se l'auto-assigner (2026-08-17) : sans ça, deux
            # agents pouvaient répondre au même ticket libre sans qu'aucun ne soit marqué
            # responsable, cassant le modèle d'assignation. Restreint au rôle sav strict
            # (décision validée) : un superviseur/admin peut dépanner un ticket libre sans se
            # l'attribuer, il garde sa vue globale et le ticket reste dans la file pour un
            # agent sav.
            if current_ticket.assigned_agent_id is None and user.role.nom_role == "sav":
                current_ticket.assigned_agent_id = user.id
    db.commit()
    db.refresh(new_message)

    if message.type_envoyeur == "sav":
        owner = db.query(models.Utilisateur).filter(models.Utilisateur.id == session.id_utilisateur).first()
        if owner:
            send_sav_reply_email(owner.email, session.title)

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
    session = db.query(models.ChatSession).filter(models.ChatSession.id == message.id_session, models.ChatSession.deleted_at.is_(None)).first()
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
