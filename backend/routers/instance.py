import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db

router = APIRouter(tags=["Instance"])

# Coupe-circuit d'abonnement (cf. models.InstanceSubscription pour le contexte). Protégé
# par un secret distinct du rôle admin classique : le rôle admin d'une instance est
# contrôlé par le client lui-même (via /setup-admin ou le bootstrap au démarrage), or c'est
# justement ce client qui pourrait un jour ne plus payer — il ne doit pas pouvoir se
# réactiver lui-même. VENDOR_KEY n'est connu que de l'opérateur de la flotte d'instances.
VENDOR_KEY = os.getenv("VENDOR_KEY")

VALID_STATUSES = ["active", "suspended"]


def _require_vendor_key(x_vendor_key: str | None) -> None:
    if not VENDOR_KEY or x_vendor_key != VENDOR_KEY:
        raise HTTPException(status_code=403, detail="Non autorisé.")


def _get_or_create_row(db: Session) -> models.InstanceSubscription:
    row = db.query(models.InstanceSubscription).filter_by(id=1).first()
    if not row:
        row = models.InstanceSubscription(id=1, status="active")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/instance/subscription-status", response_model=schemas.SubscriptionStatusResponse, summary="Consulter le statut d'abonnement de l'instance (opérateur uniquement)")
def get_subscription_status(x_vendor_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_vendor_key(x_vendor_key)
    row = _get_or_create_row(db)
    return {"status": row.status, "reason": row.reason, "updated_at": row.updated_at}


@router.put("/instance/subscription-status", response_model=schemas.SubscriptionStatusResponse, summary="Activer/suspendre l'instance (opérateur uniquement)")
def update_subscription_status(payload: schemas.SubscriptionStatusUpdateRequest, x_vendor_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_vendor_key(x_vendor_key)
    new_status = payload.status.strip().lower()
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Statut invalide, attendu : {VALID_STATUSES}")
    row = _get_or_create_row(db)
    row.status = new_status
    row.reason = payload.reason
    db.commit()
    db.refresh(row)
    return {"status": row.status, "reason": row.reason, "updated_at": row.updated_at}
