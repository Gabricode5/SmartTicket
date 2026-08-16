"""Tests du modèle Ticket (Étape 1 du chantier "refonte ticketing SAV" — modèle + migration
uniquement, aucun endpoint ne crée encore de Ticket, donc ces tests insèrent directement via
`db_session`, pas via le TestClient HTTP comme le reste de la suite."""
import pytest
from sqlalchemy.exc import IntegrityError

import models


def _make_user(db_session, *, email: str, role: str = "user") -> models.Utilisateur:
    role_row = db_session.query(models.Role).filter_by(nom_role=role).first()
    user = models.Utilisateur(
        username=email.split("@")[0], email=email, password_hash="x", id_role=role_row.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_session(db_session, user: models.Utilisateur) -> models.ChatSession:
    session = models.ChatSession(id_utilisateur=user.id, status="transferred", transfer_reason="technique")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def test_create_ticket_gets_a_sequential_number_and_new_defaults(db_session):
    user = _make_user(db_session, email="client1@example.com")
    session = _make_session(db_session, user)

    ticket = models.Ticket(session_id=session.id)
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)

    assert ticket.ticket_number >= 1000  # séquence démarrée à 1000
    assert ticket.status == "new"
    assert ticket.waiting_on == "us"
    assert ticket.priority == "normal"
    assert ticket.assigned_agent_id is None
    assert ticket.deleted_at is None


def test_ticket_numbers_are_unique_and_increment_across_tickets(db_session):
    user = _make_user(db_session, email="client2@example.com")
    session = _make_session(db_session, user)

    first = models.Ticket(session_id=session.id)
    second = models.Ticket(session_id=session.id)
    db_session.add_all([first, second])
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.ticket_number != second.ticket_number


def test_status_and_waiting_on_transition_independently(db_session):
    """Un ticket peut être in_progress ET waiting_on=customer en même temps -- ce sont deux
    dimensions distinctes, ni l'une ni l'autre ne doit contraindre les valeurs possibles de
    l'autre (cf. modèle validé le 2026-08-17)."""
    user = _make_user(db_session, email="client3@example.com")
    session = _make_session(db_session, user)
    ticket = models.Ticket(session_id=session.id)
    db_session.add(ticket)
    db_session.commit()

    ticket.status = "in_progress"
    ticket.waiting_on = "customer"
    db_session.commit()
    db_session.refresh(ticket)

    assert ticket.status == "in_progress"
    assert ticket.waiting_on == "customer"

    ticket.status = "resolved"
    db_session.commit()
    db_session.refresh(ticket)

    assert ticket.status == "resolved"
    assert ticket.waiting_on == "customer"  # inchangé par la transition de status


@pytest.mark.parametrize("column,value", [
    ("status", "bogus"),
    ("waiting_on", "bogus"),
    ("priority", "bogus"),
])
def test_invalid_enum_value_is_rejected_by_db_check_constraint(db_session, column, value):
    user = _make_user(db_session, email="client4@example.com")
    session = _make_session(db_session, user)
    ticket = models.Ticket(session_id=session.id, **{column: value})
    db_session.add(ticket)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_ticket_requires_a_valid_session_id(db_session):
    ticket = models.Ticket(session_id=999999)
    db_session.add(ticket)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_session_cascades_to_its_tickets(db_session):
    user = _make_user(db_session, email="client5@example.com")
    session = _make_session(db_session, user)
    ticket = models.Ticket(session_id=session.id)
    db_session.add(ticket)
    db_session.commit()
    ticket_id = ticket.id

    db_session.delete(session)
    db_session.commit()

    assert db_session.query(models.Ticket).filter_by(id=ticket_id).first() is None


def test_deleting_assigned_agent_unassigns_ticket_instead_of_deleting_it(db_session):
    """L'agent assigné n'est PAS le propriétaire du ticket (contrairement au client via
    session_id) -- supprimer son compte ne doit jamais faire disparaître le ticket."""
    client_user = _make_user(db_session, email="client6@example.com")
    agent = _make_user(db_session, email="agent6@example.com", role="sav")
    session = _make_session(db_session, client_user)
    ticket = models.Ticket(session_id=session.id, assigned_agent_id=agent.id)
    db_session.add(ticket)
    db_session.commit()
    ticket_id = ticket.id

    db_session.delete(agent)
    db_session.commit()

    refreshed = db_session.query(models.Ticket).filter_by(id=ticket_id).first()
    assert refreshed is not None
    assert refreshed.assigned_agent_id is None


def test_same_session_can_have_multiple_tickets_across_transfer_cycles(db_session):
    """Décision validée le 2026-08-17 : 1 ticket par cycle de transfert, pas 1 par
    conversation -- session_id n'est pas UNIQUE sur tickets."""
    user = _make_user(db_session, email="client7@example.com")
    session = _make_session(db_session, user)

    first = models.Ticket(session_id=session.id, status="closed")
    db_session.add(first)
    db_session.commit()

    second = models.Ticket(session_id=session.id)
    db_session.add(second)
    db_session.commit()  # ne doit PAS lever d'IntegrityError

    tickets = db_session.query(models.Ticket).filter_by(session_id=session.id).all()
    assert len(tickets) == 2
