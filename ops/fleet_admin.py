#!/usr/bin/env python3
"""Page de gestion de flotte — LOCALE UNIQUEMENT (cf. ops/README.md, section garde-fous).

Ne tourne que sur le poste du vendeur, n'est jamais déployée (ni backend/Dockerfile ni
frontend/Dockerfile ne copient ops/), et ne réimplémente RIEN de la logique métier :
lit ops/instances.db, appelle l'API Render en lecture via render_client.py (même client que
audit_render_resources.py) et provision()/delete_client() DIRECTEMENT — cf. provision_client.py
et delete_client.py, jamais dupliqués ici.

Usage :
    cd ops && python fleet_admin.py
    -> http://127.0.0.1:8765

CETTE PAGE PEUT CRÉER/SUSPENDRE/SUPPRIMER DES RESSOURCES RENDER PAYANTES — ne jamais
l'exposer au-delà de 127.0.0.1 (pas de --host 0.0.0.0, pas de reverse proxy public).

Création d'instance (Partie B.3) : provision() prend ~5 minutes en conditions réelles
(confirmé) — lancée dans un THREAD daemon séparé, jamais dans la requête HTTP elle-même
(qui répond immédiatement). L'état du job vit UNIQUEMENT en mémoire (_provision_jobs, un
simple dict protégé par un lock) : c'est délibérément le plus simple possible pour un
serveur local mono-utilisateur — pas de file de jobs persistante, pas de worker séparé. Deux
conséquences assumées, pas des bugs : (1) si le serveur est arrêté (Ctrl+C) pendant un
provisioning en cours, le suivi du job est perdu — mais provision() a déjà écrit la ligne
'provisioning' dans instances.db dès le début (avant le moindre appel Render) et la met à
jour au fil de l'eau, donc l'instance reste visible et son état réel retrouvable via la page
elle-même ou audit_render_resources.py, sans reprise automatique ; (2) l'historique des jobs
terminés (succès/échec) disparaît aussi au redémarrage du serveur — seul instances.db est la
source de vérité durable.
"""
import dataclasses
import logging
import re
import secrets
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import db
import delete_client
import provision_client
import render_client as render

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "fleet_admin_templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="SmartTicket — Gestion de flotte (local)")

# Protection CSRF (audit sécurité 2026-08-25) : cette console n'a ni compte ni cookie de
# session (mono-utilisateur, 127.0.0.1 uniquement) — pas de synchronizer token classique lié
# à une session possible. Un jeton unique généré au DÉMARRAGE DU PROCESSUS, réinjecté dans
# CHAQUE formulaire rendu et vérifié à CHAQUE POST, suffit à empêcher un site tiers ouvert
# dans le même navigateur de déclencher une action (suspendre/supprimer une instance,
# provisioning payant) à l'insu de l'opérateur : un attaquant ne peut pas deviner ce jeton.
# Conséquence assumée : un onglet resté ouvert avant un redémarrage du serveur voit ses
# formulaires rejetés une fois (message explicite, jamais un succès supposé) — il suffit de
# recharger la page.
_CSRF_TOKEN = secrets.token_urlsafe(32)


def _csrf_token_valid(token: str | None) -> bool:
    return secrets.compare_digest((token or "").encode(), _CSRF_TOKEN.encode())


def _reject_invalid_csrf(slug: str = "") -> RedirectResponse:
    _set_flash(action_result={
        "slug": slug, "ok": False,
        "message": "Jeton de sécurité invalide ou expiré (la page a peut-être été ouverte "
                    "avant un redémarrage du serveur) — recharge la page et réessaie.",
    })
    return RedirectResponse("/", status_code=303)


def _reject_invalid_csrf_for_creation() -> RedirectResponse:
    _set_flash(creation_result={
        "ok": False,
        "message": "Jeton de sécurité invalide ou expiré (la page a peut-être été ouverte "
                    "avant un redémarrage du serveur) — recharge la page et réessaie.",
    })
    return RedirectResponse("/", status_code=303)


@dataclasses.dataclass
class InstanceView:
    slug: str
    client_name: str
    statut: str
    plan: str | None
    date_creation: str
    backend_url: str | None
    frontend_url: str | None
    render_dashboard_backend: str | None
    render_dashboard_frontend: str | None
    render_dashboard_postgres: str | None
    render_resource_missing: bool  # True si un ID local n'a été retrouvé nulle part côté Render
    health_status: str  # "ok" | "unreachable" | "non_verifie"
    health_detail: str
    subscription_status: str  # "active" | "suspended" | "unknown" | "not_applicable"
    subscription_detail: str
    subscription_since_days: int | None  # nb de jours dans le statut actuel (suspended surtout) — None si inconnu
    can_manage_subscription: bool  # False si vendor_key ou backend_url absent — désactive les boutons
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    crm_notes: str | None


@dataclasses.dataclass
class FleetData:
    instances: list[InstanceView]
    orphans: list[dict]  # ressources Render (préfixe smartticket-) sans ligne locale
    render_available: bool  # False si RENDER_API_KEY absente/API injoignable — dégrade proprement


@dataclasses.dataclass
class ProvisionJob:
    slug: str
    client_name: str
    status: str  # "running" | "succeeded" | "failed"
    started_at: datetime
    finished_at: datetime | None = None
    setup_url: str = ""  # OK à afficher (token à usage unique, expirant) — jamais vendor_key
    welcome_email_sent: bool = False
    error: str | None = None


_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_provision_jobs: dict[str, ProvisionJob] = {}
_provision_jobs_lock = threading.Lock()


def _run_provision_job(
    *, client_name: str, slug: str, admin_email: str, postgres_plan: str,
    mistral_api_key: str, brevo_api_key: str = "",
) -> None:
    """Tourne dans un thread daemon séparé — cf. docstring du module pour le choix
    d'architecture. provision() ne devrait normalement jamais lever (elle catche déjà tout en
    interne et retourne un ProvisionResult), mais le filet de sécurité `except Exception`
    évite qu'une exception vraiment inattendue ne tue le thread en silence en laissant le job
    bloqué à 'running' pour toujours."""
    try:
        result = provision_client.provision(
            client_name=client_name, slug=slug, admin_email=admin_email, postgres_plan=postgres_plan,
            mistral_api_key=mistral_api_key, brevo_api_key=brevo_api_key,
        )
    except Exception as exc:
        logger.error("provision() a levé une exception non gérée pour '%s' : %s", slug, exc, exc_info=True)
        with _provision_jobs_lock:
            job = _provision_jobs.get(slug)
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)
        return

    with _provision_jobs_lock:
        job = _provision_jobs.get(slug)
        if not job:
            return
        job.finished_at = datetime.now(timezone.utc)
        if result.status == "active":
            job.status = "succeeded"
            job.setup_url = result.setup_url
            job.welcome_email_sent = result.welcome_email_sent
        else:
            job.status = "failed"
            job.error = result.error


_flash_lock = threading.Lock()
_flash_action_result: dict | None = None
_flash_creation_result: dict | None = None


def _set_flash(*, action_result: dict | None = None, creation_result: dict | None = None) -> None:
    """Stocke le résultat d'une action POST pour l'afficher UNE FOIS sur la page racine
    après une redirection — pattern POST-Redirect-GET. Bug réel du 2026-08-15 : les routes
    POST rendaient le HTML directement sur leur propre URL (ex: POST /instances/create) ;
    tout rafraîchissement (F5, ou le <meta refresh> de cette même page) rejouait alors la
    requête en GET sur cette URL -> 405 Method Not Allowed, alors que l'action elle-même
    avait bien réussi. Le flash vit en mémoire (jamais dans l'URL en query string : pas de
    secret ni de contenu arbitraire exposé, et surtout pas rejoué sur un F5 ultérieur de "/"
    comme le serait un flash encodé dans l'URL)."""
    global _flash_action_result, _flash_creation_result
    with _flash_lock:
        _flash_action_result = action_result
        _flash_creation_result = creation_result


def _pop_flash() -> tuple[dict | None, dict | None]:
    """Lit ET efface le flash — affiché une seule fois. Un F5 sur "/" juste après montrera
    donc une page propre sans le bandeau de résultat, jamais un 405."""
    global _flash_action_result, _flash_creation_result
    with _flash_lock:
        action_result, creation_result = _flash_action_result, _flash_creation_result
        _flash_action_result = None
        _flash_creation_result = None
    return action_result, creation_result


def _provision_jobs_view() -> list[dict]:
    with _provision_jobs_lock:
        jobs = sorted(_provision_jobs.values(), key=lambda j: j.started_at, reverse=True)
    now = datetime.now(timezone.utc)
    return [
        {
            "slug": j.slug, "client_name": j.client_name, "status": j.status,
            "elapsed_minutes": round(((j.finished_at or now) - j.started_at).total_seconds() / 60, 1),
            "setup_url": j.setup_url, "welcome_email_sent": j.welcome_email_sent, "error": j.error,
        }
        for j in jobs
    ]


def _health_check(url: str, *, timeout: float = 5.0) -> tuple[str, str]:
    """Ping direct du GET / de l'instance (healthCheckPath Render déjà en place côté
    create_web_service, cf. provision_client.py) — pas un statut Render, un vrai ping HTTP :
    Render peut rapporter un service 'live' alors que l'appli plante au runtime."""
    if not url:
        return "non_verifie", "URL absente"
    try:
        response = requests.get(url, timeout=timeout)
        if response.ok:
            return "ok", f"HTTP {response.status_code}"
        return "unreachable", f"HTTP {response.status_code}"
    except requests.exceptions.RequestException as exc:
        return "unreachable", str(exc)


def _subscription_status_check(backend_url: str, vendor_key: str, *, timeout: float = 5.0) -> tuple[str, str, str | None]:
    """GET /v1/instance/subscription-status de L'INSTANCE elle-même (pas l'API Render) —
    coupe-circuit d'abonnement déjà en place côté backend (backend/routers/instance.py),
    protégé par X-Vendor-Key. Distinct du statut Render : une instance peut être 'live' côté
    Render mais 'suspended' au niveau abonnement (402 sur /v1/* pour ses utilisateurs).

    Retourne aussi `updated_at` (chaîne ISO brute, ou None) : models.InstanceSubscription a
    déjà une colonne `updated_at` auto-maintenue (onupdate=func.now()), déjà exposée par ce
    endpoint — pas besoin d'un nouveau champ local pour savoir depuis quand une instance est
    suspendue, la donnée existe déjà côté source et est plus fiable qu'un suivi local (qui ne
    couvrirait que les actions passées par CETTE page)."""
    try:
        response = requests.get(
            f"{backend_url}/v1/instance/subscription-status",
            headers={"X-Vendor-Key": vendor_key}, timeout=timeout,
        )
        if not response.ok:
            return "unknown", f"HTTP {response.status_code}", None
        payload = response.json()
        return payload.get("status", "unknown"), "", payload.get("updated_at")
    except requests.exceptions.RequestException as exc:
        return "unknown", str(exc), None


def _days_since(iso_timestamp: str | None) -> int | None:
    """Convertit un timestamp ISO (tel que renvoyé par updated_at) en nombre de jours
    écoulés. Ne lève jamais — un format inattendu donne None plutôt qu'un crash de page."""
    if not iso_timestamp:
        return None
    try:
        then = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - then
        return max(0, delta.days)
    except ValueError:
        return None


def _subscription_status_update(backend_url: str, vendor_key: str, *, status: str, timeout: float = 10.0) -> tuple[bool, str]:
    """PUT /v1/instance/subscription-status — même route, même secret. Ne lève jamais :
    retourne (succès, message) pour que l'appelant affiche le résultat RÉEL plutôt que de
    supposer que l'action a fonctionné."""
    try:
        response = requests.put(
            f"{backend_url}/v1/instance/subscription-status",
            headers={"X-Vendor-Key": vendor_key}, json={"status": status}, timeout=timeout,
        )
        if not response.ok:
            return False, f"HTTP {response.status_code} : {response.text}"
        return True, response.json().get("status", status)
    except requests.exceptions.RequestException as exc:
        return False, str(exc)


def load_fleet_data(*, check_health: bool = True, check_subscription: bool = True) -> FleetData:
    """Coeur de lecture — fonction pure côté I/O (pas de print, pas de rendu HTML),
    testable directement sans lancer le serveur ni mocker FastAPI. Croise instances.db avec
    l'API Render EN LECTURE SEULE (list_services/list_postgres_instances, même fonctions que
    audit_render_resources.py) ; dégrade proprement si RENDER_API_KEY est absente plutôt que
    de faire planter toute la page — cette page doit rester utilisable en local-only."""
    rows = db.list_instances()

    render_by_id: dict[str, dict] = {}
    render_available = True
    try:
        render.ensure_configured()
        for service in render.list_services(name_prefix="smartticket-"):
            render_by_id[service["id"]] = service
        for postgres in render.list_postgres_instances(name_prefix="smartticket-"):
            render_by_id[postgres["id"]] = postgres
    except render.RenderAPIError as exc:
        logger.warning("Croisement Render désactivé (RENDER_API_KEY absente ou API injoignable) : %s", exc)
        render_available = False

    known_ids: set[str] = set()
    instances: list[InstanceView] = []
    for row in rows:
        local_ids = (row["render_backend_service_id"], row["render_frontend_service_id"], row["render_database_id"])
        known_ids.update(i for i in local_ids if i)

        backend = render_by_id.get(row["render_backend_service_id"])
        frontend = render_by_id.get(row["render_frontend_service_id"])
        postgres = render_by_id.get(row["render_database_id"])

        resource_missing = render_available and (
            (bool(row["render_backend_service_id"]) and not backend)
            or (bool(row["render_frontend_service_id"]) and not frontend)
            or (bool(row["render_database_id"]) and not postgres)
        )

        if check_health and row["backend_url"]:
            health_status, health_detail = _health_check(row["backend_url"])
        else:
            health_status, health_detail = "non_verifie", ""

        # vendor_key ne sort JAMAIS de cette fonction : lu ici pour l'appel serveur-à-serveur
        # vers l'instance, jamais placé sur InstanceView (qui alimente le HTML rendu) — cf.
        # garde-fou "ne pas exposer le vendor_key" (README/consigne Partie B.2).
        can_manage_subscription = bool(row["vendor_key"]) and bool(row["backend_url"])
        subscription_updated_at = None
        if row["statut"] != "active":
            subscription_status, subscription_detail = "not_applicable", ""
        elif check_subscription and can_manage_subscription:
            subscription_status, subscription_detail, subscription_updated_at = _subscription_status_check(row["backend_url"], row["vendor_key"])
        elif not can_manage_subscription:
            subscription_status, subscription_detail = "unknown", "vendor_key ou URL backend absente en registre"
        else:
            subscription_status, subscription_detail = "unknown", ""

        instances.append(InstanceView(
            slug=row["slug"], client_name=row["client_name"], statut=row["statut"],
            plan=row["plan_tarifaire"], date_creation=row["date_creation"],
            backend_url=row["backend_url"], frontend_url=row["frontend_url"],
            render_dashboard_backend=backend["dashboardUrl"] if backend else None,
            render_dashboard_frontend=frontend["dashboardUrl"] if frontend else None,
            render_dashboard_postgres=postgres["dashboardUrl"] if postgres else None,
            render_resource_missing=resource_missing,
            health_status=health_status, health_detail=health_detail,
            subscription_status=subscription_status, subscription_detail=subscription_detail,
            subscription_since_days=_days_since(subscription_updated_at) if subscription_status == "suspended" else None,
            can_manage_subscription=can_manage_subscription,
            contact_name=row["contact_name"], contact_email=row["contact_email"],
            contact_phone=row["contact_phone"], crm_notes=row["crm_notes"],
        ))

    orphans: list[dict] = []
    if render_available:
        for resource_id, resource in render_by_id.items():
            if resource_id in known_ids:
                continue
            orphans.append({
                "name": resource["name"], "id": resource_id,
                "type": resource.get("type", "postgres"),  # absent seulement sur les objets postgres
                "dashboard": resource["dashboardUrl"],
            })

    return FleetData(instances=instances, orphans=orphans, render_available=render_available)


def _render_fleet_page(request: Request) -> HTMLResponse:
    """Rendu de la page racine UNIQUEMENT — jamais appelée directement par une route POST
    (cf. _set_flash/_pop_flash : pattern POST-Redirect-GET, toute action POST redirige ici
    plutôt que de rendre le HTML sur sa propre URL)."""
    db.init_db()
    data = load_fleet_data()
    jobs = _provision_jobs_view()
    action_result, creation_result = _pop_flash()
    return templates.TemplateResponse(request, "index.html", {
        "instances": data.instances, "orphans": data.orphans, "render_available": data.render_available,
        "action_result": action_result, "creation_result": creation_result,
        "provision_jobs": jobs, "any_job_running": any(j["status"] == "running" for j in jobs),
        "postgres_plans": _postgres_plans_with_total_cost(), "default_postgres_plan": render.DEFAULT_POSTGRES_PLAN,
        "csrf_token": _CSRF_TOKEN,
    })


def _postgres_plans_with_total_cost() -> list[dict]:
    """Coût total = Postgres + backend + frontend (les 2 services web, toujours en plan
    WEB_SERVICE_PLAN — provision() ne l'expose pas comme champ de formulaire ici) — le
    Postgres seul ne reflète pas ce que paie réellement l'exploitant pour une instance."""
    web_cost = 2 * render.WEB_SERVICE_PLAN_MONTHLY_USD
    return [
        {**plan, "total_monthly_usd": plan["monthly_usd"] + web_cost}
        for plan in render.FLEET_ADMIN_POSTGRES_PLANS
    ]


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _render_fleet_page(request)


def _handle_subscription_action(slug: str, *, target_status: str, confirm_slug: str) -> None:
    """Commun à /suspend et /reactivate : même validation de confirmation, même appel HTTP
    (_subscription_status_update, jamais dupliqué), même résultat HONNÊTE déposé en flash —
    on ne suppose JAMAIS le succès, le prochain GET / ré-interroge la source (load_fleet_data()
    refait un GET frais pour CETTE instance comme pour toutes les autres)."""
    row = db.get_instance(slug)
    if not row:
        action_result = {"slug": slug, "ok": False, "message": f"Instance '{slug}' introuvable dans le registre."}
    elif confirm_slug.strip() != slug:
        # Action à impact client direct (402 pour tous les utilisateurs finaux si suspension) —
        # confirmation par saisie du slug, même motif que delete_client.py --yes absent.
        action_result = {"slug": slug, "ok": False, "message": "Confirmation invalide : le slug tapé ne correspond pas — action annulée."}
    elif not row["vendor_key"] or not row["backend_url"]:
        action_result = {"slug": slug, "ok": False, "message": "vendor_key ou URL backend absente en registre — action impossible depuis cette page."}
    else:
        ok, message = _subscription_status_update(row["backend_url"], row["vendor_key"], status=target_status)
        action_result = {"slug": slug, "ok": ok, "message": message}

    _set_flash(action_result=action_result)


@app.post("/instances/{slug}/suspend")
def suspend_instance(slug: str, confirm_slug: str = Form(...), csrf_token: str = Form("")) -> RedirectResponse:
    if not _csrf_token_valid(csrf_token):
        return _reject_invalid_csrf(slug)
    _handle_subscription_action(slug, target_status="suspended", confirm_slug=confirm_slug)
    return RedirectResponse("/", status_code=303)


@app.post("/instances/{slug}/reactivate")
def reactivate_instance(slug: str, confirm_slug: str = Form(...), csrf_token: str = Form("")) -> RedirectResponse:
    if not _csrf_token_valid(csrf_token):
        return _reject_invalid_csrf(slug)
    _handle_subscription_action(slug, target_status="active", confirm_slug=confirm_slug)
    return RedirectResponse("/", status_code=303)


@app.post("/instances/{slug}/crm")
def update_crm_route(
    slug: str,
    contact_name: str = Form(""), contact_email: str = Form(""),
    contact_phone: str = Form(""), crm_notes: str = Form(""),
    csrf_token: str = Form(""),
) -> RedirectResponse:
    """Fiche contact/notes commerciales — pas de confirmation par slug (contrairement à
    suspendre/supprimer) : aucun impact sur les utilisateurs finaux du client, juste du suivi
    interne pour le vendeur. Champs vidés dans le formulaire -> NULL en base plutôt que chaîne
    vide, cohérent avec le schéma nullable (cf. db.py)."""
    if not _csrf_token_valid(csrf_token):
        return _reject_invalid_csrf(slug)
    db.update_instance(
        slug,
        contact_name=contact_name.strip() or None,
        contact_email=contact_email.strip() or None,
        contact_phone=contact_phone.strip() or None,
        crm_notes=crm_notes.strip() or None,
    )
    return RedirectResponse("/", status_code=303)


def _handle_delete_action(slug: str, *, confirm_slug: str, confirm_destruction: str | None) -> None:
    """Action la plus dangereuse de la page : IRRÉVERSIBLE (base + toutes les données du
    client détruites). Deux confirmations distinctes requises — saisie exacte du slug (même
    motif que suspendre/réactiver) PLUS une case cochée explicitement ("je comprends que les
    données seront détruites") — plus strict que la suspension, volontairement. Appelle
    delete_client.delete_instance() : MÊME fonction que la CLI, rien réimplémenté ici."""
    row = db.get_instance(slug)
    if not row:
        action_result = {"slug": slug, "ok": False, "message": f"Instance '{slug}' introuvable dans le registre."}
    elif confirm_slug.strip() != slug:
        action_result = {"slug": slug, "ok": False, "message": "Confirmation invalide : le slug tapé ne correspond pas — suppression annulée."}
    elif confirm_destruction != "yes":
        action_result = {"slug": slug, "ok": False, "message": "Case de confirmation non cochée — suppression annulée."}
    else:
        result = delete_client.delete_instance(slug)
        if result.status == "deleted":
            action_result = {"slug": slug, "ok": True, "message": "Instance supprimée : base Postgres, service backend et service frontend retirés, ligne retirée du registre."}
        else:
            # "failed" (échec partiel, ligne conservée en 'deletion_failed' — cf.
            # delete_instance()) ou "not_found" : dans les deux cas, ne JAMAIS afficher un
            # succès qui n'a pas eu lieu.
            action_result = {"slug": slug, "ok": False, "message": result.error}

    _set_flash(action_result=action_result)


@app.post("/instances/{slug}/delete")
def delete_instance_route(
    slug: str, confirm_slug: str = Form(...), confirm_destruction: str | None = Form(None),
    csrf_token: str = Form(""),
) -> RedirectResponse:
    if not _csrf_token_valid(csrf_token):
        return _reject_invalid_csrf(slug)
    _handle_delete_action(slug, confirm_slug=confirm_slug, confirm_destruction=confirm_destruction)
    return RedirectResponse("/", status_code=303)


@app.post("/instances/create")
def create_instance_route(
    client_name: str = Form(...), slug: str = Form(...),
    admin_email: str = Form(...), postgres_plan: str = Form(render.DEFAULT_POSTGRES_PLAN),
    mistral_api_key: str = Form(...), brevo_api_key: str = Form(""),
    csrf_token: str = Form(""),
) -> RedirectResponse:
    """Lance provision() en tâche de fond (cf. docstring du module) et répond IMMÉDIATEMENT
    par une redirection — jamais d'attente synchrone des ~5 minutes que prend un
    provisioning réel, et jamais de rendu HTML directement sur cette URL de POST (sans ça,
    un F5 ou le <meta refresh> de la page suivante rejouerait ce POST en GET -> 405, bug réel
    du 2026-08-15). MÊME fonction que la CLI (provision_client.provision()), rien
    réimplémenté ici.

    mistral_api_key/brevo_api_key : clés DÉDIÉES à ce client (2026-08-19, cf. ROADMAP.md
    bloquant sécurité/RGPD n°3), créées manuellement dans les consoles Mistral/Brevo avant de
    remplir ce formulaire — plus aucun secret partagé lu depuis l'environnement du poste.

    Protégée par le même jeton CSRF que les autres actions (cf. _CSRF_TOKEN) — c'est même
    l'action la plus sensible de la page : elle crée des ressources Render RÉELLEMENT
    FACTURÉES, contrairement à la fiche CRM."""
    if not _csrf_token_valid(csrf_token):
        return _reject_invalid_csrf_for_creation()
    client_name = client_name.strip()
    slug = slug.strip().lower()
    admin_email = admin_email.strip()
    mistral_api_key = mistral_api_key.strip()
    brevo_api_key = brevo_api_key.strip()

    if not client_name or not admin_email or not mistral_api_key:
        creation_result = {"ok": False, "message": "Le nom du client, l'email admin et la clé API Mistral sont requis."}
    elif not _SLUG_PATTERN.match(slug):
        creation_result = {"ok": False, "message": f"Slug '{slug}' invalide — minuscules, chiffres et tirets uniquement, sans tiret en début/fin (ex: acme-corp)."}
    elif db.slug_exists(slug):
        # provision() referait exactement cette vérification (et refuserait de toute façon) —
        # elle est dupliquée ici UNIQUEMENT pour un retour immédiat côté formulaire, avant de
        # lancer un thread pour rien. La vérification qui compte reste celle de provision().
        creation_result = {"ok": False, "message": f"Le slug '{slug}' existe déjà dans le registre — choisis-en un autre."}
    else:
        with _provision_jobs_lock:
            _provision_jobs[slug] = ProvisionJob(
                slug=slug, client_name=client_name, status="running", started_at=datetime.now(timezone.utc),
            )
        threading.Thread(
            target=_run_provision_job,
            kwargs=dict(
                client_name=client_name, slug=slug, admin_email=admin_email, postgres_plan=postgres_plan,
                mistral_api_key=mistral_api_key, brevo_api_key=brevo_api_key,
            ),
            daemon=True,
        ).start()
        creation_result = {
            "ok": True,
            "message": f"Création de '{slug}' lancée en tâche de fond (~5 min). L'email de bienvenue partira au client à la fin — suis la progression ci-dessous.",
        }

    _set_flash(creation_result=creation_result)
    return RedirectResponse("/", status_code=303)


def main() -> int:
    db.init_db()
    print("Gestion de flotte (local uniquement) : http://127.0.0.1:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
