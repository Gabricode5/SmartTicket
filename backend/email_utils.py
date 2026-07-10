import logging
import os
import smtplib
from email.message import EmailMessage

import requests

_log = logging.getLogger(__name__)

# Priorité à l'API HTTP Brevo si une clé est fournie : contourne les blocages de ports/IP
# SMTP fréquents chez les hébergeurs PaaS (Render notamment — port 587 timeout, puis
# 525 Unauthorized IP address même avec les bons identifiants SMTP, faute d'IP de sortie
# fixe à whitelister côté Brevo). Passe par HTTPS classique, jamais bloqué. Le SMTP
# générique reste disponible en repli pour les fournisseurs sans API HTTP équivalente.
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@smartticket.app")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3005")


def _send_via_brevo_api(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    try:
        response = requests.post(
            BREVO_API_URL,
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"},
            json={
                "sender": {"name": "SmartTicket", "email": SMTP_FROM},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": text_body,
                "htmlContent": html_body,
            },
            timeout=10,
        )
        response.raise_for_status()
    except Exception:
        _log.error("Échec de l'envoi d'email (API Brevo) à %s", to_email, exc_info=True)


def _send_via_smtp(to_email: str, subject: str, text_body: str, html_body: str) -> None:
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
        _log.error("Échec de l'envoi d'email (SMTP) à %s", to_email, exc_info=True)


def send_email(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    """Envoie un email via l'API Brevo (si BREVO_API_KEY est définie), sinon en repli via
    SMTP générique (si SMTP_HOST est défini). Si aucun des deux n'est configuré (dev local,
    tests), log le contenu au lieu d'échouer — permet de développer sans compte email."""
    if BREVO_API_KEY:
        _send_via_brevo_api(to_email, subject, text_body, html_body)
        return
    if SMTP_HOST:
        _send_via_smtp(to_email, subject, text_body, html_body)
        return
    _log.info("Email non configuré (ni BREVO_API_KEY ni SMTP_HOST) — email non envoyé. À: %s | Sujet: %s\n%s", to_email, subject, text_body)


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


def send_account_invitation_email(to_email: str, username: str, token: str) -> None:
    """Compte créé en masse par un admin (import CSV, cf. routers/users.py::import_users_csv) —
    même lien/token que la réinitialisation de mot de passe (password_reset), seul le texte
    change puisque l'utilisateur n'a jamais eu de mot de passe à "réinitialiser"."""
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    text_body = (
        f"Bonjour {username},\n\n"
        f"Un compte SmartTicket vient d'être créé pour vous. Cliquez sur ce lien pour choisir votre mot de passe et vous connecter :\n{link}\n\n"
        "Ce lien expire dans 1 heure. Passé ce délai, utilisez \"Mot de passe oublié\" sur la page de connexion pour en recevoir un nouveau."
    )
    html_body = (
        f"<p>Bonjour {username},</p>"
        f"<p>Un compte SmartTicket vient d'être créé pour vous. Cliquez sur ce lien pour choisir votre mot de passe et vous connecter :</p>"
        f'<p><a href="{link}">Choisir mon mot de passe</a></p>'
        "<p>Ce lien expire dans 1 heure. Passé ce délai, utilisez \"Mot de passe oublié\" sur la page de connexion pour en recevoir un nouveau.</p>"
    )
    send_email(to_email, "Bienvenue sur SmartTicket — créez votre mot de passe", text_body, html_body)


def send_password_reset_email(to_email: str, username: str, token: str) -> None:
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    text_body = (
        f"Bonjour {username},\n\n"
        f"Vous avez demandé à réinitialiser votre mot de passe SmartTicket. Cliquez sur ce lien pour en choisir un nouveau :\n{link}\n\n"
        "Ce lien expire dans 1 heure. Si vous n'êtes pas à l'origine de cette demande, ignorez cet email — votre mot de passe reste inchangé."
    )
    html_body = (
        f"<p>Bonjour {username},</p>"
        f"<p>Vous avez demandé à réinitialiser votre mot de passe SmartTicket. Cliquez sur ce lien pour en choisir un nouveau :</p>"
        f'<p><a href="{link}">Réinitialiser mon mot de passe</a></p>'
        "<p>Ce lien expire dans 1 heure. Si vous n'êtes pas à l'origine de cette demande, ignorez cet email — votre mot de passe reste inchangé.</p>"
    )
    send_email(to_email, "Réinitialisation de votre mot de passe — SmartTicket", text_body, html_body)
