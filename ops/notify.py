"""Email de bienvenue envoyé au client à la fin du provisioning (cf. provision_client.py::
provision()) — contient le lien de setup à usage unique qui lui permet de choisir son
compte administrateur (POST /v1/setup côté backend, cf. routers/auth.py).

Volontairement indépendant de backend/email_utils.py : ops/ ne doit jamais dépendre de
backend/ (cf. ops/README.md — ce dossier n'est jamais déployé sur une instance client, son
code doit rester lisible et exécutable seul, sans installer les dépendances backend).
Duplication de quelques lignes d'appel HTTP à l'API Brevo assumée pour cette raison.
"""
import logging
import os

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
SENDER_EMAIL = os.getenv("SMTP_FROM", "no-reply@smartticket.app")


def send_welcome_email(*, admin_email: str, client_name: str, setup_url: str) -> bool:
    """Envoie le lien de setup au client. Retourne True si l'appel Brevo a réussi, False
    sinon (BREVO_API_KEY absente ou erreur HTTP) — dans les deux cas, ne lève jamais : un
    échec d'email ne doit pas faire échouer un provisioning déjà terminé côté Render, le
    lien reste de toute façon affiché en console par provision_client.py."""
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        logger.warning(
            "BREVO_API_KEY absente de l'environnement : email de bienvenue NON envoyé à %s. "
            "Le lien de setup doit être transmis manuellement au client : %s",
            admin_email, setup_url,
        )
        return False

    subject = f"Bienvenue sur SmartTicket — configurez votre compte administrateur ({client_name})"
    text_body = (
        f"Bonjour,\n\n"
        f"Votre instance SmartTicket pour {client_name} est prête. Cliquez sur ce lien pour "
        f"choisir votre nom d'utilisateur, votre email et votre mot de passe administrateur :\n"
        f"{setup_url}\n\n"
        "Ce lien est à usage unique et expire après un délai fixé côté instance (48h par défaut). "
        "Si vous ne parvenez pas à l'utiliser à temps, contactez votre fournisseur SmartTicket "
        "pour en recevoir un nouveau."
    )
    html_body = (
        f"<p>Bonjour,</p>"
        f"<p>Votre instance SmartTicket pour <strong>{client_name}</strong> est prête. "
        f"Cliquez sur ce lien pour choisir votre nom d'utilisateur, votre email et votre mot "
        f"de passe administrateur :</p>"
        f'<p><a href="{setup_url}">Configurer mon compte administrateur</a></p>'
        "<p>Ce lien est à usage unique et expire après un délai fixé côté instance (48h par "
        "défaut). Si vous ne parvenez pas à l'utiliser à temps, contactez votre fournisseur "
        "SmartTicket pour en recevoir un nouveau.</p>"
    )

    try:
        response = requests.post(
            BREVO_API_URL,
            headers={"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
            json={
                "sender": {"name": "SmartTicket", "email": SENDER_EMAIL},
                "to": [{"email": admin_email}],
                "subject": subject,
                "textContent": text_body,
                "htmlContent": html_body,
            },
            timeout=10,
        )
        response.raise_for_status()
    except Exception:
        logger.error(
            "Échec de l'envoi de l'email de bienvenue (API Brevo) à %s — lien de setup à "
            "transmettre manuellement : %s", admin_email, setup_url, exc_info=True,
        )
        return False

    logger.info("Email de bienvenue envoyé à %s.", admin_email)
    return True
