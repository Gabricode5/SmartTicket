import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    LOGIN_RATE_LIMIT,
    create_access_token,
    get_current_user,
    get_user_by_email,
    limiter,
    pwd_context,
)
from pdf_export import build_user_data_export_pdf

router = APIRouter(tags=["Authentification"])

ADMIN_SETUP_KEY = os.getenv("ADMIN_SETUP_KEY")


@router.post("/setup-admin", summary="Crée ou promeut un compte admin (nécessite X-Setup-Key)")
def setup_admin(
    payload: schemas.UserCreate,
    x_setup_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Le bootstrap admin normal se fait automatiquement au démarrage via
    # ADMIN_EMAIL/ADMIN_USERNAME/ADMIN_PASSWORD (voir main.py). Cet endpoint
    # n'est qu'un outil de secours, désactivé tant que ADMIN_SETUP_KEY n'est pas défini.
    if not ADMIN_SETUP_KEY or x_setup_key != ADMIN_SETUP_KEY:
        raise HTTPException(status_code=403, detail="Non autorisé.")
    admin_role = db.query(models.Role).filter_by(nom_role="admin").first()
    if not admin_role:
        raise HTTPException(status_code=503, detail="Rôles non initialisés, réessaie dans quelques secondes.")
    existing = db.query(models.Utilisateur).filter_by(email=payload.email).first()
    if existing:
        existing.id_role = admin_role.id
        existing.password_hash = pwd_context.hash(payload.password)
        existing.deleted_at = None
        db.commit()
        return {"message": f"Compte promu admin : {existing.email}"}
    if db.query(models.Utilisateur).filter(models.Utilisateur.username == payload.username, models.Utilisateur.deleted_at.is_(None)).first():
        raise HTTPException(status_code=400, detail="Ce username est déjà utilisé.")
    admin = models.Utilisateur(
        username=payload.username,
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
        prenom=payload.prenom,
        nom=payload.nom,
        id_role=admin_role.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {"message": f"Compte admin créé : {admin.email}"}


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED, summary="Créer un compte utilisateur")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.Utilisateur).filter(models.Utilisateur.email == user.email, models.Utilisateur.deleted_at.is_(None)).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
    if db.query(models.Utilisateur).filter(models.Utilisateur.username == user.username, models.Utilisateur.deleted_at.is_(None)).first():
        raise HTTPException(status_code=400, detail="Ce username est déjà utilisé.")
    default_role = db.query(models.Role).filter(models.Role.nom_role == "user").first()
    if not default_role:
        raise HTTPException(status_code=500, detail="Rôle par défaut introuvable")
    new_user = models.Utilisateur(
        username=user.username, email=user.email,
        password_hash=pwd_context.hash(user.password),
        prenom=user.prenom, nom=user.nom, id_role=default_role.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    role_name = db.query(models.Role.nom_role).filter(models.Role.id == new_user.id_role).scalar() or "user"
    return {"id": new_user.id, "username": new_user.username, "email": new_user.email,
            "prenom": new_user.prenom, "nom": new_user.nom, "role": role_name, "date_creation": new_user.date_creation}


@router.post("/login", summary="Se connecter et obtenir un token JWT")
@limiter.limit(LOGIN_RATE_LIMIT)
def login(request: Request, user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.Utilisateur).filter(models.Utilisateur.email == user_credentials.email, models.Utilisateur.deleted_at.is_(None)).first()
    if not user or not pwd_context.verify(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="L'email ou le mot de passe est incorrect")
    role_name = user.role.nom_role if user.role else "user"
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id, "role": role_name})
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer",
                                     "username": user.username, "user_id": user.id, "nom_role": role_name})
    cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(key="auth_token", value=access_token, httponly=True, samesite="strict",
                        secure=cookie_secure, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/")
    return response


@router.post("/logout", summary="Se déconnecter (supprime le cookie)")
def logout():
    response = JSONResponse(content={"message": "Déconnecté"})
    response.set_cookie(key="auth_token", value="", httponly=True, samesite="strict",
                        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", max_age=0, path="/")
    return response


@router.get("/me", response_model=schemas.MeResponse, summary="Obtenir le profil de l'utilisateur connecté")
def read_me(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    role_name = user.role.nom_role if user.role else "user"
    return {"id": user.id, "username": user.username, "email": user.email,
            "prenom": user.prenom, "nom": user.nom, "role": role_name, "date_creation": user.date_creation}


@router.put("/me", response_model=schemas.MeResponse, summary="Mettre à jour son profil")
def update_me(payload: schemas.MeUpdateRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(status_code=400, detail="Le username ne peut pas être vide")
        if db.query(models.Utilisateur).filter(models.Utilisateur.username == new_username, models.Utilisateur.id != user.id).first():
            raise HTTPException(status_code=400, detail="Ce username est déjà utilisé")
        user.username = new_username
    if payload.email is not None:
        new_email = payload.email.strip().lower()
        if db.query(models.Utilisateur).filter(models.Utilisateur.email == new_email, models.Utilisateur.id != user.id).first():
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
        user.email = new_email
    if payload.prenom is not None:
        user.prenom = payload.prenom.strip() if payload.prenom else None
    if payload.nom is not None:
        user.nom = payload.nom.strip() if payload.nom else None
    db.commit()
    db.refresh(user)
    role_name = user.role.nom_role if user.role else "user"
    return {"id": user.id, "username": user.username, "email": user.email,
            "prenom": user.prenom, "nom": user.nom, "role": role_name, "date_creation": user.date_creation}


@router.get("/me/export", summary="Exporter toutes ses données personnelles en PDF (RGPD Art. 15 et 20)")
def export_my_data(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    sessions = db.query(models.ChatSession).filter(
        models.ChatSession.id_utilisateur == user.id,
        models.ChatSession.deleted_at.is_(None),
    ).order_by(models.ChatSession.date_creation.asc()).all()

    sessions_data = []
    for s in sessions:
        messages = db.query(models.ChatMessage).filter(
            models.ChatMessage.id_session == s.id,
        ).order_by(models.ChatMessage.date_creation.asc()).all()
        sessions_data.append({
            "id": s.id,
            "title": s.title,
            "status": s.status,
            "messages": [
                {
                    "auteur": m.type_envoyeur,
                    "contenu": m.contenu,
                    "date": m.date_creation.strftime("%d/%m/%Y %H:%M") if m.date_creation else None,
                }
                for m in messages
            ],
        })

    pdf_bytes = build_user_data_export_pdf(user, sessions_data)
    filename = f"mes-donnees-smartticket-{datetime.utcnow().strftime('%Y-%m-%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/me/password", summary="Changer son mot de passe")
def update_my_password(payload: schemas.MePasswordUpdateRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not pwd_context.verify(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit contenir au moins 6 caractères")
    user.password_hash = pwd_context.hash(payload.new_password)
    db.commit()
    return {"message": "Mot de passe mis à jour"}
