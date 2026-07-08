"""Notifications in-app (+ email best-effort) pour les événements ticket : réponse SAV,
transfert vers l'équipe humaine. Les fonctions `queue_*` ajoutent la notification à la
session SQLAlchemy en cours (elles ne commitent pas elles-mêmes) pour rester dans la même
transaction que l'action qui les déclenche. L'email n'est envoyé qu'après le commit
appelant, côté routeur — jamais avant, pour ne pas notifier un événement qui, finalement,
n'a pas été persisté."""
from sqlalchemy.orm import Session

import models
from email_utils import send_email

NOTIFIED_AGENT_ROLES = ["sav", "superviseur", "admin"]


def queue_sav_reply(db: Session, session: models.ChatSession) -> None:
    title = session.title or "Sans titre"
    db.add(models.Notification(
        id_utilisateur=session.id_utilisateur,
        type="sav_reply",
        message=f"Un agent SAV a répondu à votre ticket « {title} ».",
        id_session=session.id,
    ))


def queue_session_transferred(db: Session, session: models.ChatSession, reason_label: str) -> None:
    agents = db.query(models.Utilisateur).join(models.Role).filter(
        models.Role.nom_role.in_(NOTIFIED_AGENT_ROLES),
        models.Utilisateur.deleted_at.is_(None),
    ).all()
    title = session.title or "Sans titre"
    message = f"Nouveau ticket transféré : « {title} » ({reason_label})."
    for agent in agents:
        db.add(models.Notification(id_utilisateur=agent.id, type="session_transferred", message=message, id_session=session.id))


def send_sav_reply_email(owner_email: str, session_title: str | None) -> None:
    title = session_title or "Sans titre"
    text = f"Un agent SAV a répondu à votre ticket « {title} ». Connectez-vous à SmartTicket pour voir la réponse."
    html = f"<p>Un agent SAV a répondu à votre ticket « {title} ». Connectez-vous à SmartTicket pour voir la réponse.</p>"
    send_email(owner_email, "Nouvelle réponse SAV — SmartTicket", text, html)
