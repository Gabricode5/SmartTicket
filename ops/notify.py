"""Email de bienvenue envoyé au client à la fin du provisioning (cf. provision_client.py::
provision()) — contient le lien de setup à usage unique qui lui permet de choisir son
compte administrateur (POST /v1/setup côté backend, cf. routers/auth.py).

Volontairement indépendant de backend/email_utils.py : ops/ ne doit jamais dépendre de
backend/ (cf. ops/README.md — ce dossier n'est jamais déployé sur une instance client, son
code doit rester lisible et exécutable seul, sans installer les dépendances backend).
Duplication de quelques lignes d'appel HTTP à l'API Brevo assumée pour cette raison.
"""
import logging

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_welcome_email(*, admin_email: str, client_name: str, setup_url: str, instance_url: str, api_key: str, sender_email: str) -> bool:
    """Envoie le lien de setup au client, ainsi que l'URL permanente de son instance (à
    conserver pour se reconnecter par la suite — seul le lien de setup expire). Retourne
    True si l'appel Brevo a réussi, False sinon (api_key vide ou erreur HTTP) — dans les
    deux cas, ne lève jamais : un échec d'email ne doit pas faire échouer un provisioning
    déjà terminé côté Render, le lien reste de toute façon affiché en console par
    provision_client.py.

    instance_url est la même valeur que frontend_url côté provision_client.py, transmise
    explicitement (jamais reconstruite depuis setup_url) — les deux URLs ont des durées de
    vie différentes et ne doivent pas être confondues par le client.

    api_key/sender_email DÉDIÉS à ce client, transmis explicitement par provision() (2026-08-19)
    — avant ce chantier, cette fonction lisait BREVO_API_KEY/SMTP_FROM depuis l'environnement
    de l'opérateur, indépendamment de backend_env : l'email de bienvenue restait mutualisé
    même après avoir isolé le reste des secrets par instance. Plus de lecture d'environnement
    ici du tout."""
    if not api_key:
        logger.warning(
            "Aucune clé Brevo fournie pour cette instance : email de bienvenue NON envoyé à "
            "%s. Le lien de setup et l'URL de l'instance doivent être transmis manuellement "
            "au client : %s (setup), %s (instance)",
            admin_email, setup_url, instance_url,
        )
        return False

    subject = f"Bienvenue sur Tiqia — configurez votre compte administrateur ({client_name})"
    text_body = (
        f"Bonjour,\n\n"
        f"Votre instance Tiqia pour {client_name} est prête.\n\n"
        "ÉTAPE 1 — À FAIRE MAINTENANT\n"
        "Cliquez sur ce lien pour choisir votre nom d'utilisateur, votre email et votre mot "
        f"de passe administrateur :\n"
        f"{setup_url}\n"
        "Ce lien est à usage unique et expire après un délai fixé côté instance (48h par défaut). "
        "Si vous ne parvenez pas à l'utiliser à temps, contactez votre fournisseur Tiqia "
        "pour en recevoir un nouveau.\n\n"
        "À CONSERVER — l'adresse de votre espace\n"
        f"Voici l'adresse de votre espace Tiqia, à conserver pour vous reconnecter : "
        f"{instance_url}. Contrairement au lien ci-dessus, cette adresse est permanente : "
        "nous vous conseillons de l'ajouter à vos favoris dès maintenant."
    )
    html_body = (
        f"<p>Bonjour,</p>"
        f"<p>Votre instance Tiqia pour <strong>{client_name}</strong> est prête.</p>"
        '<div style="border:2px solid #4f46e5;border-radius:8px;padding:16px;margin:16px 0;">'
        '<p style="margin:0 0 8px;font-weight:bold;color:#4f46e5;">Étape 1 — à faire maintenant</p>'
        "<p>Cliquez sur ce lien pour choisir votre nom d'utilisateur, votre email et votre mot "
        "de passe administrateur :</p>"
        f'<p><a href="{setup_url}">Configurer mon compte administrateur</a></p>'
        "<p style=\"font-size:0.9em;color:#555;\">Ce lien est à usage unique et expire après un "
        "délai fixé côté instance (48h par défaut). Si vous ne parvenez pas à l'utiliser à "
        "temps, contactez votre fournisseur Tiqia pour en recevoir un nouveau.</p>"
        "</div>"
        '<div style="border:2px solid #059669;border-radius:8px;padding:16px;margin:16px 0;">'
        '<p style="margin:0 0 8px;font-weight:bold;color:#059669;">À conserver — l\'adresse de votre espace</p>'
        "<p>Voici l'adresse de votre espace Tiqia, à conserver pour vous reconnecter : "
        f'<a href="{instance_url}">{instance_url}</a>.</p>'
        "<p style=\"font-size:0.9em;color:#555;\">Contrairement au lien ci-dessus, cette adresse "
        "est <strong>permanente</strong> : nous vous conseillons de l'ajouter à vos favoris dès "
        "maintenant.</p>"
        "</div>"
    )

    try:
        response = requests.post(
            BREVO_API_URL,
            headers={"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
            json={
                "sender": {"name": "Tiqia", "email": sender_email},
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
