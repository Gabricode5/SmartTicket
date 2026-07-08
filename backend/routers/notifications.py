from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import get_current_user, get_user_by_email

router = APIRouter(tags=["Notifications"])


def _to_response(notification: models.Notification) -> dict:
    return {
        "id": notification.id,
        "type": notification.type,
        "message": notification.message,
        "id_session": notification.id_session,
        "read": notification.read_at is not None,
        "date_creation": notification.date_creation,
    }


@router.get("/notifications", response_model=list[schemas.NotificationResponse], summary="Lister mes notifications récentes")
def list_notifications(limit: int = 30, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    rows = db.query(models.Notification).filter(
        models.Notification.id_utilisateur == user.id,
    ).order_by(models.Notification.date_creation.desc()).limit(min(max(limit, 1), 100)).all()
    return [_to_response(n) for n in rows]


@router.get("/notifications/unread-count", summary="Nombre de notifications non lues")
def unread_count(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    count = db.query(models.Notification).filter(
        models.Notification.id_utilisateur == user.id,
        models.Notification.read_at.is_(None),
    ).count()
    return {"count": count}


@router.post("/notifications/read-all", summary="Marquer toutes mes notifications comme lues")
def mark_all_read(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    db.query(models.Notification).filter(
        models.Notification.id_utilisateur == user.id,
        models.Notification.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()})
    db.commit()
    return {"ok": True}


@router.patch("/notifications/{notification_id}/read", response_model=schemas.NotificationResponse, summary="Marquer une notification comme lue")
def mark_read(notification_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.id_utilisateur == user.id,
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return _to_response(notification)
