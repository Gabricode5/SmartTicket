from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import get_current_user, get_user_by_email

router = APIRouter(tags=["Utilisateurs"])


@router.get("/users", response_model=list[schemas.UserListResponse], summary="Lister les utilisateurs (admin/sav)")
def list_users(role: str | None = None, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not requester.role or requester.role.nom_role not in ["admin", "sav"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    query = db.query(models.Utilisateur).join(models.Role)
    if role:
        query = query.filter(models.Role.nom_role == role)
    return [{"id": u.id, "username": u.username, "email": u.email, "prenom": u.prenom, "nom": u.nom,
             "role": u.role.nom_role if u.role else "user"} for u in query.all()]


@router.put("/users/{user_id}/role", response_model=schemas.UserListResponse, summary="Modifier le rôle d'un utilisateur (admin)")
def update_user_role(user_id: int, payload: schemas.UserRoleUpdateRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not requester.role or requester.role.nom_role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    target = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if requester.id == target.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre rôle")
    new_role = payload.role.strip().lower()
    if new_role not in ["user", "sav", "admin"]:
        raise HTTPException(status_code=400, detail="Rôle invalide")
    role_row = db.query(models.Role).filter(models.Role.nom_role == new_role).first()
    if not role_row:
        raise HTTPException(status_code=400, detail="Rôle introuvable")
    target.id_role = role_row.id
    db.commit()
    db.refresh(target)
    return {"id": target.id, "username": target.username, "email": target.email,
            "prenom": target.prenom, "nom": target.nom, "role": target.role.nom_role if target.role else "user"}


@router.put("/users/{user_id}", response_model=schemas.UserListResponse, summary="Modifier un utilisateur (admin)")
def update_user_by_admin(user_id: int, payload: schemas.UserAdminUpdateRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not requester.role or requester.role.nom_role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    target = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(status_code=400, detail="Le username ne peut pas être vide")
        if db.query(models.Utilisateur).filter(models.Utilisateur.username == new_username, models.Utilisateur.id != target.id).first():
            raise HTTPException(status_code=400, detail="Ce username est déjà utilisé")
        target.username = new_username
    if payload.email is not None:
        new_email = payload.email.strip().lower()
        if db.query(models.Utilisateur).filter(models.Utilisateur.email == new_email, models.Utilisateur.id != target.id).first():
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
        target.email = new_email
    if payload.prenom is not None:
        target.prenom = payload.prenom.strip() if payload.prenom else None
    if payload.nom is not None:
        target.nom = payload.nom.strip() if payload.nom else None
    if payload.role is not None:
        next_role = payload.role.strip().lower()
        if next_role not in ["user", "sav", "admin"]:
            raise HTTPException(status_code=400, detail="Rôle invalide")
        if requester.id == target.id and next_role != "admin":
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas retirer votre rôle admin")
        role_row = db.query(models.Role).filter(models.Role.nom_role == next_role).first()
        if not role_row:
            raise HTTPException(status_code=400, detail="Rôle introuvable")
        target.id_role = role_row.id
    db.commit()
    db.refresh(target)
    return {"id": target.id, "username": target.username, "email": target.email,
            "prenom": target.prenom, "nom": target.nom, "role": target.role.nom_role if target.role else "user"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer un utilisateur (admin)")
def delete_user_by_admin(user_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not requester.role or requester.role.nom_role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    target = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if requester.id == target.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    db.delete(target)
    db.commit()
