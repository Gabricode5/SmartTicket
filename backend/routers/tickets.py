from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
import schemas
from constants import VALID_TICKET_STATUSES, VALID_TICKET_WAITING_ON
from database import get_db
from dependencies import can_manage_sav_team, get_current_user, get_user_by_email, is_admin_or_sav

router = APIRouter(tags=["Tickets"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _require_agent(db: Session, current_user: str) -> models.Utilisateur:
    user = get_user_by_email(db, current_user)
    if not user or not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    return user


def _scope_by_role(query, user: models.Utilisateur):
    """Cloisonnement strict (précision validée le 2026-08-18) : un sav (ni superviseur ni
    admin) ne voit QUE la file (tickets non-assignés) + ses propres tickets assignés --
    jamais un ticket assigné à un autre agent, même en lecture. superviseur/admin voient
    tout."""
    if can_manage_sav_team(user):
        return query
    return query.filter(or_(models.Ticket.assigned_agent_id.is_(None), models.Ticket.assigned_agent_id == user.id))


def _get_visible_ticket_or_404(db: Session, user: models.Utilisateur, ticket_id: int) -> models.Ticket:
    ticket = _scope_by_role(
        db.query(models.Ticket).filter(models.Ticket.id == ticket_id, models.Ticket.deleted_at.is_(None)), user,
    ).first()
    if not ticket:
        # Un ticket assigné à un autre agent est 404 pour un sav, pas 403 : le cloisonnement
        # strict ne doit même pas révéler qu'il existe (cf. règle de permission validée).
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    return ticket


def _serialize_many(db: Session, tickets: list[models.Ticket]) -> list[dict]:
    """Batché (une requête pour toutes les sessions, une pour tous les utilisateurs
    impliqués) plutôt qu'un aller-retour DB par ticket -- même esprit que list_sessions
    (routers/sessions.py) pour has_sav_reply."""
    if not tickets:
        return []
    session_ids = {t.session_id for t in tickets}
    sessions = {s.id: s for s in db.query(models.ChatSession).filter(models.ChatSession.id.in_(session_ids)).all()}
    client_ids = {s.id_utilisateur for s in sessions.values()}
    agent_ids = {t.assigned_agent_id for t in tickets if t.assigned_agent_id}
    users = {}
    wanted_ids = client_ids | agent_ids
    if wanted_ids:
        users = {u.id: u for u in db.query(models.Utilisateur).filter(models.Utilisateur.id.in_(wanted_ids)).all()}

    result = []
    for t in tickets:
        session = sessions.get(t.session_id)
        client = users.get(session.id_utilisateur) if session else None
        agent = users.get(t.assigned_agent_id) if t.assigned_agent_id else None
        result.append({
            "id": t.id, "ticket_number": t.ticket_number, "session_id": t.session_id,
            "status": t.status, "waiting_on": t.waiting_on, "assigned_agent_id": t.assigned_agent_id,
            "priority": t.priority, "reason": t.reason, "context_cutoff_message_id": t.context_cutoff_message_id,
            "created_at": t.created_at, "updated_at": t.updated_at,
            "client_username": client.username if client else None,
            "client_email": client.email if client else None,
            "assigned_agent_username": agent.username if agent else None,
        })
    return result


@router.get("/tickets", response_model=schemas.TicketListResponse, summary="Lister les tickets (filtres + pagination)")
def list_tickets(
    ticket_status: Optional[str] = Query(None, alias="status"),
    waiting_on: Optional[str] = Query(None),
    assigned_agent_id: Optional[int] = Query(None),
    unassigned: Optional[bool] = Query(None, description="true = uniquement la file (non-assignés)"),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = _require_agent(db, current_user)
    if ticket_status is not None and ticket_status not in VALID_TICKET_STATUSES:
        raise HTTPException(status_code=400, detail=f"status invalide. Valeurs acceptées : {', '.join(sorted(VALID_TICKET_STATUSES))}")
    if waiting_on is not None and waiting_on not in VALID_TICKET_WAITING_ON:
        raise HTTPException(status_code=400, detail=f"waiting_on invalide. Valeurs acceptées : {', '.join(sorted(VALID_TICKET_WAITING_ON))}")
    if priority is not None and priority not in {"normal", "urgent"}:
        raise HTTPException(status_code=400, detail="priority invalide. Valeurs acceptées : normal, urgent")

    query = _scope_by_role(db.query(models.Ticket).filter(models.Ticket.deleted_at.is_(None)), user)
    if ticket_status is not None:
        query = query.filter(models.Ticket.status == ticket_status)
    if waiting_on is not None:
        query = query.filter(models.Ticket.waiting_on == waiting_on)
    if priority is not None:
        query = query.filter(models.Ticket.priority == priority)
    if unassigned:
        query = query.filter(models.Ticket.assigned_agent_id.is_(None))
    elif assigned_agent_id is not None:
        query = query.filter(models.Ticket.assigned_agent_id == assigned_agent_id)

    total = query.count()
    tickets = query.order_by(models.Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": _serialize_many(db, tickets), "total": total, "page": page, "page_size": page_size}


@router.get("/tickets/search", response_model=schemas.TicketListResponse, summary="Rechercher par numéro de ticket ou par client (nom/email)")
def search_tickets(
    q: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    current_user: str = Depends(get_current_user), db: Session = Depends(get_db),
):
    user = _require_agent(db, current_user)
    query_str = q.strip()
    if not query_str:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    base = _scope_by_role(db.query(models.Ticket).filter(models.Ticket.deleted_at.is_(None)), user)

    if query_str.isdigit():
        base = base.filter(models.Ticket.ticket_number == int(query_str))
    else:
        matching_user_ids = [row[0] for row in db.query(models.Utilisateur.id).filter(
            models.Utilisateur.deleted_at.is_(None),
            or_(
                models.Utilisateur.username.ilike(f"%{_escape_like(query_str)}%", escape="\\"),
                models.Utilisateur.email.ilike(f"%{_escape_like(query_str)}%", escape="\\"),
            ),
        ).all()]
        if not matching_user_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        matching_session_ids = [row[0] for row in db.query(models.ChatSession.id).filter(
            models.ChatSession.id_utilisateur.in_(matching_user_ids),
        ).all()]
        if not matching_session_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        base = base.filter(models.Ticket.session_id.in_(matching_session_ids))

    total = base.count()
    tickets = base.order_by(models.Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": _serialize_many(db, tickets), "total": total, "page": page, "page_size": page_size}


@router.get("/tickets/{ticket_id}", response_model=schemas.TicketResponse, summary="Détail d'un ticket (conversation liée via session_id + contexte IA via context_cutoff_message_id)")
def get_ticket(ticket_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _require_agent(db, current_user)
    ticket = _get_visible_ticket_or_404(db, user, ticket_id)
    return _serialize_many(db, [ticket])[0]


@router.patch("/tickets/{ticket_id}/status", response_model=schemas.TicketResponse, summary="Changer le statut (indépendant de waiting_on)")
def update_ticket_status(
    ticket_id: int, payload: schemas.TicketStatusUpdateRequest,
    current_user: str = Depends(get_current_user), db: Session = Depends(get_db),
):
    user = _require_agent(db, current_user)
    if payload.status not in VALID_TICKET_STATUSES:
        raise HTTPException(status_code=400, detail=f"status invalide. Valeurs acceptées : {', '.join(sorted(VALID_TICKET_STATUSES))}")
    ticket = _get_visible_ticket_or_404(db, user, ticket_id)
    ticket.status = payload.status
    db.commit()
    db.refresh(ticket)
    return _serialize_many(db, [ticket])[0]


@router.patch("/tickets/{ticket_id}/waiting_on", response_model=schemas.TicketResponse, summary="Changer waiting_on (indépendant du statut)")
def update_ticket_waiting_on(
    ticket_id: int, payload: schemas.TicketWaitingOnUpdateRequest,
    current_user: str = Depends(get_current_user), db: Session = Depends(get_db),
):
    user = _require_agent(db, current_user)
    if payload.waiting_on not in VALID_TICKET_WAITING_ON:
        raise HTTPException(status_code=400, detail=f"waiting_on invalide. Valeurs acceptées : {', '.join(sorted(VALID_TICKET_WAITING_ON))}")
    ticket = _get_visible_ticket_or_404(db, user, ticket_id)
    ticket.waiting_on = payload.waiting_on
    db.commit()
    db.refresh(ticket)
    return _serialize_many(db, [ticket])[0]


@router.post("/tickets/{ticket_id}/assign", response_model=schemas.TicketResponse, summary="S'auto-assigner un ticket libre (sav), ou assigner/réaffecter à n'importe quel agent (superviseur/admin)")
def assign_ticket(
    ticket_id: int, payload: schemas.TicketAssignRequest,
    current_user: str = Depends(get_current_user), db: Session = Depends(get_db),
):
    user = _require_agent(db, current_user)
    # La visibilité fait déjà l'essentiel du travail pour un sav : un ticket assigné à un
    # autre agent est 404 avant même d'arriver ici (cf. _get_visible_ticket_or_404), donc
    # "prendre le ticket d'un collègue" est structurellement impossible pour un sav, pas
    # juste refusé après coup.
    ticket = _get_visible_ticket_or_404(db, user, ticket_id)

    if can_manage_sav_team(user):
        target_id = payload.agent_id if payload.agent_id is not None else user.id
        target = db.query(models.Utilisateur).filter(
            models.Utilisateur.id == target_id, models.Utilisateur.deleted_at.is_(None),
        ).first()
        if not target or not is_admin_or_sav(target):
            raise HTTPException(status_code=400, detail="Cible d'assignation invalide (doit être un compte sav/superviseur/admin actif).")
    else:
        if payload.agent_id is not None and payload.agent_id != user.id:
            raise HTTPException(status_code=403, detail="Un agent ne peut s'assigner qu'à lui-même.")
        target_id = user.id

    ticket.assigned_agent_id = target_id
    db.commit()
    db.refresh(ticket)
    return _serialize_many(db, [ticket])[0]
