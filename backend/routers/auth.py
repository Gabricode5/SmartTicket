import logging
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
    ADMIN_SETUP_RATE_LIMIT,
    FORGOT_PASSWORD_RATE_LIMIT,
    LOGIN_RATE_LIMIT,
    REGISTER_RATE_LIMIT,
    RESEND_VERIFICATION_RATE_LIMIT,
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    decode_email_verification_token,
    decode_password_reset_token,
    get_current_user,
    get_user_by_email,
    is_guest_email,
    limiter,
    pwd_context,
)
from email_utils import send_password_reset_email, send_verification_email
from pdf_export import build_user_data_export_pdf

router = APIRouter(tags=["Authentification"])
logger = logging.getLogger(__name__)

ADMIN_SETUP_KEY = os.getenv("ADMIN_SETUP_KEY")


@router.post("/setup-admin", summary="[Dev/test uniquement] Crée ou promeut un compte admin (nécessite X-Setup-Key)")
@limiter.limit(ADMIN_SETUP_RATE_LIMIT)
def setup_admin(
    request: Request,
    payload: schemas.UserCreate,
    x_setup_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Porte de secours réservée au dev/test local et à la CI (cf. backend/tests/conftest.py,
    qui fixe ADMIN_SETUP_KEY pour toute la suite) : le bootstrap admin normal se fait
    automatiquement au démarrage via ADMIN_EMAIL/ADMIN_USERNAME/ADMIN_PASSWORD (voir main.py),
    et le flux client réel passe par POST /v1/setup à token unique et expirant (cf. plus haut).

    INERTE PAR DÉFAUT sur toute instance de production : ops/provision_client.py ne pose plus
    ADMIN_SETUP_KEY sur les instances client provisionnées pour la flotte (cf. décision
    documentée dans docs/FLEET_PROVISIONING_PLAN.md) — sans cette variable d'environnement,
    la vérification ci-dessous échoue systématiquement (403), quel que soit x_setup_key. Ne
    JAMAIS définir ADMIN_SETUP_KEY sur une instance client réelle : contrairement à
    /v1/setup, cette route n'expire jamais et peut réécrire le mot de passe de N'IMPORTE
    QUEL email existant en le promouvant admin."""
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
        existing.email_verified = True
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
        email_verified=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {"message": f"Compte admin créé : {admin.email}"}


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED, summary="Créer un compte utilisateur")
# Callable plutôt que la chaîne directement : slowapi l'appelle à chaque requête au lieu
# de figer la valeur une fois pour toutes au chargement du module, ce qui permet de tester
# réellement le comportement "limite dépassée" (monkeypatch de REGISTER_RATE_LIMIT).
@limiter.limit(lambda: REGISTER_RATE_LIMIT)
def register_user(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Pas de filtre deleted_at ici : la contrainte UNIQUE en base porte sur email/username
    # sur toutes les lignes, y compris les comptes soft-deleted (RGPD, purgés après 30j).
    # Filtrer sur deleted_at IS NULL laisserait passer ce cas jusqu'au commit, qui échouerait
    # alors avec une IntegrityError non gérée (500) au lieu de ce message 400 propre.
    if db.query(models.Utilisateur).filter(models.Utilisateur.email == user.email).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
    if db.query(models.Utilisateur).filter(models.Utilisateur.username == user.username).first():
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

    token = create_email_verification_token(new_user.id, new_user.email)
    send_verification_email(new_user.email, new_user.username, token)

    return {"id": new_user.id, "username": new_user.username, "email": new_user.email,
            "prenom": new_user.prenom, "nom": new_user.nom, "role": role_name,
            "email_verified": new_user.email_verified, "date_creation": new_user.date_creation}


@router.get("/verify-email", summary="Confirmer une adresse email via le lien reçu par mail")
def verify_email(token: str, db: Session = Depends(get_db)):
    payload = decode_email_verification_token(token)
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.id == payload.get("user_id"),
        models.Utilisateur.email == payload.get("sub"),
        models.Utilisateur.deleted_at.is_(None),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
    return {"message": "Adresse email vérifiée avec succès."}


@router.post("/resend-verification", summary="Renvoyer l'email de vérification")
@limiter.limit(RESEND_VERIFICATION_RATE_LIMIT)
def resend_verification(request: Request, payload: schemas.ResendVerificationRequest, db: Session = Depends(get_db)):
    # Message générique dans tous les cas (compte inexistant, déjà vérifié, ou envoi réel) —
    # évite de laisser deviner par ce endpoint public si un email est déjà inscrit.
    generic_response = {"message": "Si un compte existe avec cet email et n'est pas encore vérifié, un email vient d'être envoyé."}
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.email == payload.email.strip().lower(),
        models.Utilisateur.deleted_at.is_(None),
    ).first()
    if user and not user.email_verified:
        token = create_email_verification_token(user.id, user.email)
        send_verification_email(user.email, user.username, token)
    return generic_response


@router.post("/forgot-password", summary="Demander un lien de réinitialisation de mot de passe")
@limiter.limit(FORGOT_PASSWORD_RATE_LIMIT)
def forgot_password(request: Request, payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    # Message générique dans tous les cas (compte inexistant ou envoi réel) — même logique
    # anti-énumération que /resend-verification.
    generic_response = {"message": "Si un compte existe avec cet email, un lien de réinitialisation vient d'être envoyé."}
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.email == payload.email.strip().lower(),
        models.Utilisateur.deleted_at.is_(None),
    ).first()
    if user:
        token = create_password_reset_token(user.id, user.email)
        send_password_reset_email(user.email, user.username, token)
    return generic_response


@router.post("/reset-password", summary="Réinitialiser son mot de passe via le lien reçu par mail")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    token_payload = decode_password_reset_token(payload.token)
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit contenir au moins 6 caractères")
    user = db.query(models.Utilisateur).filter(
        models.Utilisateur.id == token_payload.get("user_id"),
        models.Utilisateur.email == token_payload.get("sub"),
        models.Utilisateur.deleted_at.is_(None),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    user.password_hash = pwd_context.hash(payload.new_password)
    db.commit()
    return {"message": "Mot de passe réinitialisé avec succès."}


# Volontairement plus strict que le reste de l'app (6 caractères ailleurs — /reset-password,
# /me/password, /me/claim) : ce mot de passe protège le compte admin d'une instance client
# entière, jamais le contraire. Uniquement la longueur (pas de règle de complexité — usine à
# gaz inutile) + un filtre sur une poignée de mots de passe très communs.
ADMIN_SETUP_MIN_PASSWORD_LENGTH = 12
_COMMON_PASSWORDS = frozenset({
    "password", "password123", "administrator", "changeme123",
    "azertyuiop", "qwertyuiop123", "smartticket", "welcome123",
    "motdepasse", "motdepasse123", "letmein12345", "changeme123!",
})


@router.post("/setup", summary="Finaliser la configuration du compte admin via un lien de setup à usage unique")
@limiter.limit(ADMIN_SETUP_RATE_LIMIT)
def setup_account(request: Request, payload: schemas.AdminSetupRequest, db: Session = Depends(get_db)):
    """Amorçage d'un compte admin provisionné via ops/provision_client.py (flotte
    d'instances) : le client choisit lui-même son mot de passe, aucun mot de passe n'a
    jamais transité en clair côté opérateur. Le token (admin_setup_token) est distinct du
    JWT applicatif — un secret stocké en base, à usage unique (admin_setup_token_used_at)
    et expirant (admin_setup_token_expires_at), jamais renvoyé par aucune route de l'API."""
    if len(payload.password) < ADMIN_SETUP_MIN_PASSWORD_LENGTH:
        logger.warning("POST /v1/setup rejeté : mot de passe trop court (%d caractères, %d requis)", len(payload.password), ADMIN_SETUP_MIN_PASSWORD_LENGTH)
        raise HTTPException(status_code=400, detail=f"Le mot de passe doit contenir au moins {ADMIN_SETUP_MIN_PASSWORD_LENGTH} caractères")
    if payload.password.lower() in _COMMON_PASSWORDS:
        logger.warning("POST /v1/setup rejeté : mot de passe trop commun")
        raise HTTPException(status_code=400, detail="Ce mot de passe est trop commun, choisis-en un autre.")

    user = db.query(models.Utilisateur).filter(models.Utilisateur.admin_setup_token == payload.token).first()
    if not user:
        # Jamais le token lui-même dans les logs — uniquement sa longueur et le nombre de
        # comptes qui ont un token d'amorçage en attente sur CETTE base, pour distinguer
        # "aucun admin en attente de setup ici" (la requête a peut-être atteint la mauvaise
        # instance/le mauvais backend) de "un admin en attente existe mais avec un autre
        # token" (vraie divergence de valeur).
        pending_count = db.query(models.Utilisateur).filter(models.Utilisateur.admin_setup_token.isnot(None)).count()
        logger.warning(
            "POST /v1/setup rejeté : invalid_token (longueur du token reçu=%d, %d compte(s) "
            "avec un token d'amorçage en attente sur cette instance)",
            len(payload.token), pending_count,
        )
        raise HTTPException(status_code=400, detail={"code": "invalid_token", "message": "Lien de configuration invalide."})
    if user.admin_setup_token_used_at is not None:
        logger.warning("POST /v1/setup rejeté : token_already_used (compte %s, consommé le %s)", user.email, user.admin_setup_token_used_at)
        raise HTTPException(status_code=400, detail={"code": "token_already_used", "message": "Ce lien a déjà été utilisé."})
    if user.admin_setup_token_expires_at and user.admin_setup_token_expires_at.replace(tzinfo=None) < datetime.utcnow():
        logger.warning(
            "POST /v1/setup rejeté : token_expired (compte %s, expiré depuis le %s, maintenant %s)",
            user.email, user.admin_setup_token_expires_at, datetime.utcnow(),
        )
        raise HTTPException(status_code=400, detail={"code": "token_expired", "message": "Ce lien a expiré. Contactez votre fournisseur SmartTicket pour en recevoir un nouveau."})

    new_username = payload.username.strip()
    new_email = payload.email.strip().lower()
    if not new_username:
        logger.warning("POST /v1/setup rejeté : nom d'utilisateur vide (compte %s)", user.email)
        raise HTTPException(status_code=400, detail="Le nom d'utilisateur ne peut pas être vide.")
    if db.query(models.Utilisateur).filter(models.Utilisateur.username == new_username, models.Utilisateur.id != user.id).first():
        logger.warning("POST /v1/setup rejeté : nom d'utilisateur déjà utilisé (compte %s)", user.email)
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est déjà utilisé.")
    if db.query(models.Utilisateur).filter(models.Utilisateur.email == new_email, models.Utilisateur.id != user.id).first():
        logger.warning("POST /v1/setup rejeté : email déjà utilisé (compte %s tentait de passer à %s)", user.email, new_email)
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")

    # Consommation du token et écriture du mot de passe posées sur le même objet `user` en
    # mémoire puis persistées par un unique db.commit() ci-dessous : une seule transaction
    # SQL, un seul UPDATE. Impossible d'obtenir "token consommé sans mot de passe posé" ou
    # l'inverse — soit les deux sont écrits ensemble, soit rien ne l'est (rollback implicite
    # de SQLAlchemy si le commit échoue).
    user.username = new_username
    user.email = new_email
    user.password_hash = pwd_context.hash(payload.password)
    user.email_verified = True
    user.admin_setup_token_used_at = datetime.utcnow()
    db.commit()
    return {"message": "Configuration terminée. Vous pouvez maintenant vous connecter."}


@router.post("/login", summary="Se connecter et obtenir un token JWT")
@limiter.limit(LOGIN_RATE_LIMIT)
def login(request: Request, user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.Utilisateur).filter(models.Utilisateur.email == user_credentials.email, models.Utilisateur.deleted_at.is_(None)).first()
    if not user or not pwd_context.verify(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="L'email ou le mot de passe est incorrect")
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "email_not_verified", "message": "Adresse email non vérifiée. Consultez votre boîte de réception."},
        )
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
            "prenom": user.prenom, "nom": user.nom, "role": role_name,
            "email_verified": user.email_verified, "is_guest": is_guest_email(user.email),
            "date_creation": user.date_creation}


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
    email_changed = False
    if payload.email is not None:
        new_email = payload.email.strip().lower()
        if db.query(models.Utilisateur).filter(models.Utilisateur.email == new_email, models.Utilisateur.id != user.id).first():
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
        if new_email != user.email:
            email_changed = True
            user.email = new_email
            # Une nouvelle adresse doit être re-vérifiée — on ne peut pas hériter de la
            # confiance accordée à l'ancienne, sous peine de permettre de basculer vers
            # une adresse qu'on ne possède pas réellement.
            user.email_verified = False
    if payload.prenom is not None:
        user.prenom = payload.prenom.strip() if payload.prenom else None
    if payload.nom is not None:
        user.nom = payload.nom.strip() if payload.nom else None
    db.commit()
    db.refresh(user)
    if email_changed:
        token = create_email_verification_token(user.id, user.email)
        send_verification_email(user.email, user.username, token)
    role_name = user.role.nom_role if user.role else "user"
    return {"id": user.id, "username": user.username, "email": user.email,
            "prenom": user.prenom, "nom": user.nom, "role": role_name,
            "email_verified": user.email_verified, "is_guest": is_guest_email(user.email),
            "date_creation": user.date_creation}


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
            "date_creation": s.date_creation.strftime("%d/%m/%Y") if s.date_creation else None,
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


@router.post("/me/claim", summary="Réclamer un compte invité (lui donner un vrai email et mot de passe)")
def claim_guest_account(payload: schemas.ClaimAccountRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_guest_email(user.email):
        raise HTTPException(status_code=400, detail="Ce compte n'est pas un compte invité à réclamer.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 6 caractères")
    new_email = payload.email.strip().lower()
    if db.query(models.Utilisateur).filter(models.Utilisateur.email == new_email, models.Utilisateur.id != user.id).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

    # Un compte invité n'a pas de mot de passe connaissable (généré aléatoirement à la
    # création) — on ne demande donc pas le mot de passe actuel ici, contrairement à
    # /me/password. La possession d'une session valide pour ce compte précis (le cookie)
    # tient lieu de preuve, exactement comme pour n'importe quelle autre action de /me.
    user.email = new_email
    user.password_hash = pwd_context.hash(payload.password)
    user.email_verified = False
    db.commit()
    db.refresh(user)

    token = create_email_verification_token(user.id, user.email)
    send_verification_email(user.email, user.username, token)

    # Le JWT existant contient l'ancien email dans son claim `sub` — get_current_user ne
    # le retrouverait plus en base après ce changement. On réémet un cookie immédiatement
    # pour que la session en cours continue de fonctionner sans déconnexion surprise.
    role_name = user.role.nom_role if user.role else "user"
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id, "role": role_name})
    response = JSONResponse(content={
        "id": user.id, "username": user.username, "email": user.email,
        "prenom": user.prenom, "nom": user.nom, "role": role_name,
        "email_verified": user.email_verified, "is_guest": False,
        "date_creation": user.date_creation.isoformat(),
    })
    cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(key="auth_token", value=access_token, httponly=True, samesite="strict",
                        secure=cookie_secure, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/")
    return response
