"""Gestion des pôles (feature/poles, étape 4) -- CRUD réservé au super admin (rôle admin
existant, décision A). Tout derrière POLES_ENABLED : ces endpoints renvoient 403 si la
feature n'est pas activée sur l'instance, pour ne jamais laisser un opérateur créer des
pôles orphelins qu'aucun filtre RAG/ingestion ne consultera tant que le flag reste false.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import POLES_ENABLED, get_current_user, get_user_by_email, is_super_admin

router = APIRouter(tags=["Pôles"])


def _require_super_admin_with_poles_enabled(db: Session, current_user: str) -> models.Utilisateur:
    if not POLES_ENABLED:
        raise HTTPException(status_code=403, detail="Le système de pôles n'est pas activé sur cette instance.")
    requester = get_user_by_email(db, current_user)
    if not is_super_admin(requester):
        raise HTTPException(status_code=403, detail="Accès refusé — réservé au super admin.")
    return requester


@router.get("/poles", response_model=list[schemas.PoleResponse], summary="Lister les pôles (super admin)")
def list_poles(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_super_admin_with_poles_enabled(db, current_user)
    return db.query(models.Pole).order_by(models.Pole.nom).all()


@router.post("/poles", response_model=schemas.PoleResponse, status_code=201, summary="Créer un pôle (super admin)")
def create_pole(payload: schemas.PoleCreate, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_super_admin_with_poles_enabled(db, current_user)
    nom = payload.nom.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom du pôle ne peut pas être vide.")
    if db.query(models.Pole).filter(models.Pole.nom == nom).first():
        raise HTTPException(status_code=400, detail="Un pôle porte déjà ce nom.")
    pole = models.Pole(nom=nom)
    db.add(pole)
    db.commit()
    db.refresh(pole)
    return pole


@router.put("/poles/{pole_id}", response_model=schemas.PoleResponse, summary="Renommer un pôle (super admin)")
def rename_pole(pole_id: int, payload: schemas.PoleUpdate, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_super_admin_with_poles_enabled(db, current_user)
    pole = db.query(models.Pole).filter(models.Pole.id == pole_id).first()
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle introuvable.")
    nom = payload.nom.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom du pôle ne peut pas être vide.")
    if db.query(models.Pole).filter(models.Pole.nom == nom, models.Pole.id != pole_id).first():
        raise HTTPException(status_code=400, detail="Un pôle porte déjà ce nom.")
    pole.nom = nom
    db.commit()
    db.refresh(pole)
    return pole


@router.delete("/poles/{pole_id}", status_code=204, summary="Supprimer un pôle (super admin)")
def delete_pole(pole_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_super_admin_with_poles_enabled(db, current_user)
    pole = db.query(models.Pole).filter(models.Pole.id == pole_id).first()
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle introuvable.")
    if pole.is_global:
        raise HTTPException(
            status_code=400,
            detail="Le pôle 'Général' ne peut pas être supprimé — c'est le pôle de rattachement par défaut, "
                   "utilisé par la migration et par l'ingestion admin dans le pôle commun.",
        )

    # Aucune donnée/utilisateur ne doit devenir orphelin ou disparaître du RAG (même
    # philosophie que la migration initiale, règle 5) : tout ce qui appartenait au pôle
    # supprimé est réaffecté au pôle "Général" avant la suppression. Nécessaire aussi pour
    # knowledge_base.pole_id, NOT NULL depuis l'étape 3 -- un simple ON DELETE SET NULL sur
    # la FK échouerait avec une violation de contrainte. On ne va chercher "Général" (et
    # n'exige sa présence) que s'il y a réellement quelque chose à réaffecter -- un pôle
    # vide (jamais utilisé) doit rester supprimable même si "Général" n'existe pas encore.
    kb_count = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.pole_id == pole_id).count()
    user_count = db.query(models.Utilisateur).filter(models.Utilisateur.pole_id == pole_id).count()
    if kb_count or user_count:
        general = db.query(models.Pole).filter_by(is_global=True).first()
        if not general:
            raise HTTPException(status_code=500, detail="Pôle 'Général' introuvable — la migration n'a pas encore été exécutée.")
        db.query(models.KnowledgeBase).filter(models.KnowledgeBase.pole_id == pole_id).update(
            {"pole_id": general.id}, synchronize_session=False,
        )
        db.query(models.Utilisateur).filter(models.Utilisateur.pole_id == pole_id).update(
            {"pole_id": general.id}, synchronize_session=False,
        )
    # manager_poles pointant vers ce pôle : cascade automatique via la FK ON DELETE CASCADE.
    db.delete(pole)
    db.commit()


@router.put("/users/{user_id}/manager-poles", response_model=list[schemas.PoleResponse], summary="Assigner un superviseur à des pôles en tant que manager (super admin)")
def assign_manager_poles(user_id: int, payload: schemas.ManagerPoleAssignRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_super_admin_with_poles_enabled(db, current_user)
    target = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id, models.Utilisateur.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    if not target.role or target.role.nom_role != "superviseur":
        raise HTTPException(status_code=400, detail="Seul un superviseur peut être assigné comme manager de pôles.")

    pole_ids = set(payload.pole_ids)
    if pole_ids:
        found = {row.id for row in db.query(models.Pole.id).filter(models.Pole.id.in_(pole_ids)).all()}
        missing = pole_ids - found
        if missing:
            raise HTTPException(status_code=400, detail=f"Pôle(s) introuvable(s) : {sorted(missing)}")
        global_ids = {
            row[0] for row in db.query(models.Pole.id).filter(models.Pole.is_global.is_(True)).all()
        }
        if pole_ids & global_ids:
            raise HTTPException(
                status_code=400,
                detail="Le pôle 'Général' est réservé au super admin — il ne peut pas être assigné à un manager (décision E).",
            )

    db.query(models.ManagerPole).filter(models.ManagerPole.manager_id == user_id).delete(synchronize_session=False)
    for pole_id in pole_ids:
        db.add(models.ManagerPole(manager_id=user_id, pole_id=pole_id))
    db.commit()

    return db.query(models.Pole).filter(models.Pole.id.in_(pole_ids)).order_by(models.Pole.nom).all()
