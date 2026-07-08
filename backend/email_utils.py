import logging
import os
import smtplib
from email.message import EmailMessage

_log = logging.getLogger(__name__)

# SMTP générique (Brevo, SendGrid, Mailgun, Gmail avec mot de passe d'application...) plutôt
# qu'un SDK propriétaire — fonctionne avec n'importe quel fournisseur sans dépendance ajoutée,
# adapté à un hébergement Render où aucun service d'email n'est fourni nativement.
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@smartticket.app")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3005")


def send_email(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    """Envoie un email via SMTP. Si SMTP_HOST n'est pas configuré (dev local, tests),
    log le contenu au lieu d'échouer — permet de développer sans compte SMTP."""
    if not SMTP_HOST:
        _log.info("SMTP non configuré — email non envoyé. À: %s | Sujet: %s\n%s", to_email, subject, text_body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
    except Exception:
        _log.error("Échec de l'envoi d'email à %s", to_email, exc_info=True)


def send_verification_email(to_email: str, username: str, token: str) -> None:
    link = f"{FRONTEND_URL}/verify-email?token={token}"
    text_body = (
        f"Bonjour {username},\n\n"
        f"Merci de confirmer votre adresse email pour activer votre compte SmartTicket :\n{link}\n\n"
        "Ce lien expire dans 48 heures. Si vous n'êtes pas à l'origine de cette inscription, ignorez cet email."
    )
    html_body = (
        f"<p>Bonjour {username},</p>"
        f"<p>Merci de confirmer votre adresse email pour activer votre compte SmartTicket :</p>"
        f'<p><a href="{link}">Confirmer mon adresse email</a></p>'
        "<p>Ce lien expire dans 48 heures. Si vous n'êtes pas à l'origine de cette inscription, ignorez cet email.</p>"
    )
    send_email(to_email, "Confirmez votre adresse email — SmartTicket", text_body, html_body)
