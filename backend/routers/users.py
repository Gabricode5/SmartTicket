import csv
import io
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import (
    GUEST_EMAIL_DOMAIN, MAX_CSV_IMPORT_ROWS, can_manage_sav_team,
    create_password_reset_token, get_current_user, get_user_by_email,
    is_admin_or_sav, pwd_context,
)
from email_utils import send_account_invitation_email

router = APIRouter(tags=["Utilisateurs"])


class _CsvUserRow(BaseModel):
    """Une ligne du CSV importé — mêmes champs que schemas.UserCreate, sans le mot de passe
    (généré aléatoirement, l'utilisateur le choisit via le lien reçu par email)."""
    email: EmailStr
    username: str
    prenom: str | None = None
    nom: str | None = None


@router.get("/users", response_model=list[schemas.UserListResponse], summary="Lister les utilisateurs (admin/sav/superviseur)")
def list_users(role: str | None = None, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not is_admin_or_sav(requester):
        raise HTTPException(status_code=403, detail="Accès refusé")
    # Comptes invités (chat anonyme B2B2C, cf. POST /v1/sessions/guest) exclus de la
    # gestion des utilisateurs — ce sont des comptes techniques éphémères, pas des comptes
    # à administrer, et ils peuvent être nombreux avant leur purge automatique.
    query = db.query(models.Utilisateur).join(models.Role).filter(
        models.Utilisateur.deleted_at.is_(None),
        ~models.Utilisateur.email.like(f"%{GUEST_EMAIL_DOMAIN}"),
    )
    if role:
        query = query.filter(models.Role.nom_role == role)
    return [{"id": u.id, "username": u.username, "email": u.email, "prenom": u.prenom, "nom": u.nom,
             "role": u.role.nom_role if u.role else "user"} for u in query.all()]


@router.post("/users/import-csv", response_model=schemas.CsvImportResponse, summary="Importer des utilisateurs depuis un fichier CSV (admin)")
async def import_users_csv(file: UploadFile = File(...), current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not requester.role or requester.role.nom_role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers .csv sont acceptés.")

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Repli latin-1 : les exports CSV d'ERP français utilisent souvent Windows-1252
        # plutôt que l'UTF-8 attendu par défaut.
        text = raw_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Fichier CSV vide ou illisible.")
    normalized_fieldnames = {(f or "").strip().lower() for f in reader.fieldnames}
    if "email" not in normalized_fieldnames or "username" not in normalized_fieldnames:
        raise HTTPException(status_code=400, detail="Colonnes requises manquantes : 'email' et 'username'.")

    rows = list(reader)
    if len(rows) > MAX_CSV_IMPORT_ROWS:
        raise HTTPException(status_code=400, detail=f"Trop de lignes ({len(rows)}) — maximum {MAX_CSV_IMPORT_ROWS} par import.")

    default_role = db.query(models.Role).filter(models.Role.nom_role == "user").first()
    if not default_role:
        raise HTTPException(status_code=500, detail="Rôle par défaut introuvable")

    seen_emails: set[str] = set()
    seen_usernames: set[str] = set()
    skipped: list[schemas.CsvImportSkippedRow] = []
    created = 0

    for line_number, raw_row in enumerate(rows, start=2):  # ligne 1 = en-têtes
        normalized_row = {
            (k or "").strip().lower(): (v.strip() if isinstance(v, str) else "")
            for k, v in raw_row.items()
        }
        raw_email = normalized_row.get("email", "")
        try:
            parsed = _CsvUserRow(
                email=raw_email,
                username=normalized_row.get("username", ""),
                prenom=normalized_row.get("prenom") or None,
                nom=normalized_row.get("nom") or None,
            )
        except ValidationError:
            skipped.append(schemas.CsvImportSkippedRow(row=line_number, email=raw_email, reason="email ou username invalide"))
            continue

        email = parsed.email.lower()
        username = parsed.username

        if not username:
            skipped.append(schemas.CsvImportSkippedRow(row=line_number, email=email, reason="username manquant"))
            continue
        if email in seen_emails or username in seen_usernames:
            skipped.append(schemas.CsvImportSkippedRow(row=line_number, email=email, reason="doublon dans le fichier"))
            continue
        # Pas de filtre deleted_at : la contrainte UNIQUE en base s'applique à toutes les
        # lignes, même raison que le fix appliqué à POST /register (cf. ROADMAP.md).
        if db.query(models.Utilisateur).filter(models.Utilisateur.email == email).first():
            skipped.append(schemas.CsvImportSkippedRow(row=line_number, email=email, reason="email déjà utilisé"))
            continue
        if db.query(models.Utilisateur).filter(models.Utilisateur.username == username).first():
            skipped.append(schemas.CsvImportSkippedRow(row=line_number, email=email, reason="username déjà utilisé"))
            continue

        seen_emails.add(email)
        seen_usernames.add(username)

        try:
            new_user = models.Utilisateur(
                username=username,
                email=email,
                # Mot de passe aléatoire jamais communiqué — même pattern que les comptes
                # invités (routers/sessions.py) : l'utilisateur choisit son propre mot de
                # passe via le lien reçu par email, il n'y a jamais de mot de passe initial
                # à transmettre en clair.
                password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
                prenom=parsed.prenom,
                nom=parsed.nom,
                id_role=default_role.id,
                # Import vetté par un admin depuis les données internes de l'entreprise (ERP)
                # — pas de boucle de vérification d'email classique nécessaire, contrairement
                # à une inscription publique.
                email_verified=True,
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
        except Exception:
            db.rollback()
            skipped.append(schemas.CsvImportSkippedRow(row=line_number, email=email, reason="erreur d'enregistrement"))
            continue

        created += 1
        token = create_password_reset_token(new_user.id, new_user.email)
        send_account_invitation_email(new_user.email, new_user.username, token)

    return {"total_rows": len(rows), "created": created, "skipped": skipped}


@router.put("/users/{user_id}/role", response_model=schemas.UserListResponse, summary="Modifier le rôle d'un utilisateur (admin, ou superviseur pour user<->sav)")
def update_user_role(user_id: int, payload: schemas.UserRoleUpdateRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not can_manage_sav_team(requester):
        raise HTTPException(status_code=403, detail="Accès refusé")
    target = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id, models.Utilisateur.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if requester.id == target.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre rôle")
    new_role = payload.role.strip().lower()
    if new_role not in ["user", "sav", "superviseur", "admin"]:
        raise HTTPException(status_code=400, detail="Rôle invalide")

    is_admin_requester = requester.role.nom_role == "admin"
    if not is_admin_requester:
        # Un superviseur ne peut ni toucher un compte admin, ni promouvoir vers admin —
        # il ne gère que la bascule user <-> sav.
        if target.role and target.role.nom_role == "admin":
            raise HTTPException(status_code=403, detail="Un superviseur ne peut pas modifier un compte administrateur")
        if new_role not in ["user", "sav"]:
            raise HTTPException(status_code=403, detail="Un superviseur ne peut promouvoir que vers user ou sav")

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
    target = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id, models.Utilisateur.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(status_code=400, detail="Le username ne peut pas être vide")
        if db.query(models.Utilisateur).filter(models.Utilisateur.username == new_username, models.Utilisateur.id != target.id, models.Utilisateur.deleted_at.is_(None)).first():
            raise HTTPException(status_code=400, detail="Ce username est déjà utilisé")
        target.username = new_username
    if payload.email is not None:
        new_email = payload.email.strip().lower()
        if db.query(models.Utilisateur).filter(models.Utilisateur.email == new_email, models.Utilisateur.id != target.id, models.Utilisateur.deleted_at.is_(None)).first():
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
        target.email = new_email
    if payload.prenom is not None:
        target.prenom = payload.prenom.strip() if payload.prenom else None
    if payload.nom is not None:
        target.nom = payload.nom.strip() if payload.nom else None
    if payload.role is not None:
        next_role = payload.role.strip().lower()
        if next_role not in ["user", "sav", "superviseur", "admin"]:
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
    target = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id, models.Utilisateur.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if requester.id == target.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    now = datetime.utcnow()
    target.deleted_at = now
    db.query(models.ChatSession).filter(
        models.ChatSession.id_utilisateur == target.id,
        models.ChatSession.deleted_at.is_(None),
    ).update({"deleted_at": now})
    db.commit()
