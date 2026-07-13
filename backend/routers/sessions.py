import os
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

import models
import schemas
from constants import REASON_LABELS, VALID_REASONS
from database import get_db
from dependencies import (
    ACCESS_TOKEN_EXPIRE_MINUTES, EMBED_MODEL, GUEST_EMAIL_DOMAIN, GUEST_SESSION_RATE_LIMIT,
    INDEX_CLOSED_TICKETS, MISTRAL_MODEL, REQUEST_TIMEOUT,
    SUMMARY_MAX_CHARS, SUMMARY_MAX_MESSAGES,
    TRANSCRIPT_CHUNK_OVERLAP, TRANSCRIPT_CHUNK_SIZE, TRANSCRIPT_MAX_CHARS,
    chunk_text, create_access_token, get_current_user, get_user_by_email,
    is_admin_or_sav, limiter, pwd_context, sanitize_text,
)
from mistral_client import embed_text, generate_text
from notifications import queue_session_transferred

router = APIRouter(tags=["Sessions"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.post("/sessions", response_model=schemas.ChatSessionResponse, summary="Créer une session de chat")
def create_session(session_data: schemas.ChatSessionCreate, user_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id, models.Utilisateur.deleted_at.is_(None)).first()
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


@router.post("/sessions/guest", summary="Démarrer une conversation anonyme (compte invité créé silencieusement)")
# Callable plutôt que la chaîne directement, comme /register — voir le commentaire associé
# dans routers/auth.py (slowapi fige sinon la valeur au chargement du module).
@limiter.limit(lambda: GUEST_SESSION_RATE_LIMIT)
def create_guest_session(request: Request, db: Session = Depends(get_db)):
    """Chat public B2B2C sans inscription préalable : crée un compte "fantôme" (email
    factice sous GUEST_EMAIL_DOMAIN, mot de passe aléatoire jamais communiqué, auto-vérifié
    puisqu'il n'y a pas de vrai email à confirmer) et une session, puis authentifie
    directement le navigateur — identique du point de vue du reste du code à un compte
    normal (aucune vérification d'ownership à adapter ailleurs). Le visiteur peut plus tard
    "réclamer" ce compte via POST /v1/me/claim pour lui donner un vrai email/mot de passe."""
    default_role = db.query(models.Role).filter(models.Role.nom_role == "user").first()
    if not default_role:
        raise HTTPException(status_code=500, detail="Rôle par défaut introuvable")

    suffix = uuid.uuid4().hex[:12]
    guest = models.Utilisateur(
        username=f"guest_{suffix}",
        email=f"guest-{suffix}{GUEST_EMAIL_DOMAIN}",
        password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
        id_role=default_role.id,
        email_verified=True,
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)

    new_session = models.ChatSession(id_utilisateur=guest.id, title="Nouvelle conversation")
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    access_token = create_access_token(data={"sub": guest.email, "user_id": guest.id, "role": "user"})
    response = JSONResponse(content={
        "access_token": access_token, "token_type": "bearer",
        "username": guest.username, "user_id": guest.id, "nom_role": "user",
        "session": jsonable_encoder(schemas.ChatSessionResponse.model_validate(new_session)),
    })
    cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(key="auth_token", value=access_token, httponly=True, samesite="strict",
                        secure=cookie_secure, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/")
    return response


@router.get("/sessions", response_model=list[schemas.ChatSessionResponse], summary="Lister les sessions d'un utilisateur")
def list_sessions(user_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id, models.Utilisateur.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and requester.id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    sessions = db.query(models.ChatSession).filter(
        models.ChatSession.id_utilisateur == user_id,
        models.ChatSession.deleted_at.is_(None),
    ).order_by(models.ChatSession.date_creation.desc()).all()
    session_ids = [s.id for s in sessions]
    sav_ids: set[int] = set()
    if session_ids:
        sav_ids = {row[0] for row in db.query(models.ChatMessage.id_session).filter(
            models.ChatMessage.id_session.in_(session_ids),
            models.ChatMessage.type_envoyeur == "sav",
        ).distinct().all()}
    return [
        {
            "id": s.id,
            "id_utilisateur": s.id_utilisateur,
            "title": s.title,
            "status": s.status,
            "transfer_reason": s.transfer_reason,
            "date_creation": s.date_creation,
            "has_sav_reply": s.id in sav_ids,
        }
        for s in sessions
    ]


@router.get("/sessions/search", response_model=list[schemas.SessionSearchResult], summary="Recherche full-text dans l'historique des conversations")
def search_sessions(user_id: int, q: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    query = q.strip()
    if not query:
        return []
    user = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id, models.Utilisateur.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and requester.id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")

    # 1. Messages dont le contenu correspond à la recherche (full-text Postgres),
    # restreints aux sessions de l'utilisateur ciblé. On garde le meilleur extrait par session.
    message_rows = db.execute(
        text("""
            SELECT m.id_session AS id_session,
                   ts_headline('french', m.contenu, plainto_tsquery('french', :q),
                               'MaxWords=25, MinWords=10, ShortWord=3, MaxFragments=1') AS snippet,
                   ts_rank(to_tsvector('french', m.contenu), plainto_tsquery('french', :q)) AS rank
            FROM chat_messages m
            JOIN chat_sessions s ON s.id = m.id_session
            WHERE s.id_utilisateur = :user_id
              AND s.deleted_at IS NULL
              AND to_tsvector('french', m.contenu) @@ plainto_tsquery('french', :q)
            ORDER BY rank DESC
        """),
        {"q": query, "user_id": user_id},
    ).mappings().all()

    snippet_by_session: dict[int, str] = {}
    for row in message_rows:
        snippet_by_session.setdefault(row["id_session"], row["snippet"])

    # 2. Sessions à retourner : celles dont un message a matché, plus celles dont
    # le titre correspond directement (recherche simple, pas besoin de full-text ici).
    sessions = db.query(models.ChatSession).filter(
        models.ChatSession.id_utilisateur == user_id,
        models.ChatSession.deleted_at.is_(None),
        or_(
            models.ChatSession.id.in_(list(snippet_by_session.keys())),
            models.ChatSession.title.ilike(f"%{_escape_like(query)}%", escape="\\"),
        ),
    ).order_by(models.ChatSession.date_creation.desc()).all()

    return [
        {
            "id": s.id,
            "id_utilisateur": s.id_utilisateur,
            "title": s.title,
            "status": s.status,
            "transfer_reason": s.transfer_reason,
            "date_creation": s.date_creation,
            "snippet": snippet_by_session.get(s.id),
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une session")
def delete_session(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id, models.ChatSession.deleted_at.is_(None)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and session.id_utilisateur != requester.id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    session.deleted_at = datetime.utcnow()
    db.commit()


@router.post("/sessions/{session_id}/close", response_model=schemas.ChatSessionResponse, summary="Clôturer une session (génère un résumé IA et indexe le transcript)")
def close_session(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id, models.ChatSession.deleted_at.is_(None)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    requester = get_user_by_email(db, current_user)
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if not is_admin_or_sav(requester) and session.id_utilisateur != requester.id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if getattr(session, "status", "open") == "closed":
        return session

    # Indexer le transcript/résumé d'un ticket clos dans la base de connaissances partagée
    # expose son contenu (potentiellement des données personnelles du client final) aux
    # futures questions de n'importe quel autre utilisateur — désactivé par défaut, cf.
    # INDEX_CLOSED_TICKETS dans dependencies.py.
    if INDEX_CLOSED_TICKETS:
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
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id, models.ChatSession.deleted_at.is_(None)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    if session.id_utilisateur != user.id and not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    if session.status != "open":
        raise HTTPException(status_code=400, detail="Cette session ne peut pas être transférée.")
    session.status = "transferred"
    session.transfer_reason = payload.reason
    reason_label = REASON_LABELS.get(payload.reason, payload.reason)
    db.add(models.ChatMessage(id_session=session_id, type_envoyeur="ai", contenu=f"Vous avez été mis en relation avec un agent humain. Raison : {reason_label}."))
    queue_session_transferred(db, session, reason_label)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "id_utilisateur": session.id_utilisateur, "title": session.title, "status": session.status, "transfer_reason": session.transfer_reason, "date_creation": session.date_creation}


@router.post("/sessions/{session_id}/resolve", response_model=schemas.ChatSessionResponse, summary="Rétablir l'IA après un transfert humain")
def resolve_session(session_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id, models.ChatSession.deleted_at.is_(None)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    is_owner = session.id_utilisateur == user.id
    if not is_owner and not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    if session.status != "transferred":
        raise HTTPException(status_code=400, detail="Cette session n'est pas en transfert.")
    # Le client ne peut reprendre la main que si un agent SAV a déjà répondu — avant ça, il doit
    # attendre en file d'attente (sinon il pourrait court-circuiter le transfert qu'il vient de demander).
    has_sav_reply = db.query(models.ChatMessage).filter(
        models.ChatMessage.id_session == session_id, models.ChatMessage.type_envoyeur == "sav"
    ).first() is not None
    if is_owner and not is_admin_or_sav(user) and not has_sav_reply:
        raise HTTPException(status_code=400, detail="En attente de la réponse d'un agent SAV.")
    session.status = "open"
    session.transfer_reason = None
    resolved_by = "l'agent SAV" if not is_owner else "le client"
    db.add(models.ChatMessage(id_session=session_id, type_envoyeur="ai", contenu=f"La conversation a été rétablie avec l'assistant IA (par {resolved_by})."))
    db.commit()
    db.refresh(session)
    return {"id": session.id, "id_utilisateur": session.id_utilisateur, "title": session.title, "status": session.status, "transfer_reason": session.transfer_reason, "date_creation": session.date_creation}


@router.get("/sessions/transferred", summary="Lister les sessions en attente d'un agent humain")
def get_transferred_sessions(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    rows = db.query(models.ChatSession, models.Utilisateur.username).join(models.Utilisateur, models.ChatSession.id_utilisateur == models.Utilisateur.id).filter(
        models.ChatSession.status == "transferred",
        models.ChatSession.deleted_at.is_(None),
        models.Utilisateur.deleted_at.is_(None),
    ).order_by(models.ChatSession.date_creation.desc()).all()
    return [{"id": s.id, "title": s.title, "status": s.status, "transfer_reason": s.transfer_reason, "date_creation": s.date_creation, "username": username} for s, username in rows]
