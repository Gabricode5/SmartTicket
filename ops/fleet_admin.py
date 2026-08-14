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

CETTE PAGE PEUT CRÉER/SUSPENDRE/SUPPRIMER DES RESSOURCES RENDER PAYANTES DÈS LA PARTIE B.2/B.3
— ne jamais l'exposer au-delà de 127.0.0.1 (pas de --host 0.0.0.0, pas de reverse proxy public).
"""
import dataclasses
import logging
import sys
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import db
import render_client as render

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "fleet_admin_templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="SmartTicket — Gestion de flotte (local)")


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
    can_manage_subscription: bool  # False si vendor_key ou backend_url absent — désactive les boutons


@dataclasses.dataclass
class FleetData:
    instances: list[InstanceView]
    orphans: list[dict]  # ressources Render (préfixe smartticket-) sans ligne locale
    render_available: bool  # False si RENDER_API_KEY absente/API injoignable — dégrade proprement


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


def _subscription_status_check(backend_url: str, vendor_key: str, *, timeout: float = 5.0) -> tuple[str, str]:
    """GET /v1/instance/subscription-status de L'INSTANCE elle-même (pas l'API Render) —
    coupe-circuit d'abonnement déjà en place côté backend (backend/routers/instance.py),
    protégé par X-Vendor-Key. Distinct du statut Render : une instance peut être 'live' côté
    Render mais 'suspended' au niveau abonnement (402 sur /v1/* pour ses utilisateurs)."""
    try:
        response = requests.get(
            f"{backend_url}/v1/instance/subscription-status",
            headers={"X-Vendor-Key": vendor_key}, timeout=timeout,
        )
        if not response.ok:
            return "unknown", f"HTTP {response.status_code}"
        return response.json().get("status", "unknown"), ""
    except requests.exceptions.RequestException as exc:
        return "unknown", str(exc)


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
        if row["statut"] != "active":
            subscription_status, subscription_detail = "not_applicable", ""
        elif check_subscription and can_manage_subscription:
            subscription_status, subscription_detail = _subscription_status_check(row["backend_url"], row["vendor_key"])
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
            can_manage_subscription=can_manage_subscription,
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    db.init_db()
    data = load_fleet_data()
    return templates.TemplateResponse(request, "index.html", {
        "instances": data.instances, "orphans": data.orphans, "render_available": data.render_available,
        "action_result": None,
    })


def _handle_subscription_action(request: Request, slug: str, *, target_status: str, confirm_slug: str) -> HTMLResponse:
    """Commun à /suspend et /reactivate : même validation de confirmation, même appel HTTP
    (_subscription_status_update, jamais dupliqué), même ré-affichage HONNÊTE du résultat —
    on ne suppose JAMAIS le succès, on ré-interroge la source après coup (load_fleet_data()
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

    data = load_fleet_data()
    return templates.TemplateResponse(request, "index.html", {
        "instances": data.instances, "orphans": data.orphans, "render_available": data.render_available,
        "action_result": action_result,
    })


@app.post("/instances/{slug}/suspend", response_class=HTMLResponse)
def suspend_instance(request: Request, slug: str, confirm_slug: str = Form(...)) -> HTMLResponse:
    return _handle_subscription_action(request, slug, target_status="suspended", confirm_slug=confirm_slug)


@app.post("/instances/{slug}/reactivate", response_class=HTMLResponse)
def reactivate_instance(request: Request, slug: str, confirm_slug: str = Form(...)) -> HTMLResponse:
    return _handle_subscription_action(request, slug, target_status="active", confirm_slug=confirm_slug)


def main() -> int:
    db.init_db()
    print("Gestion de flotte (local uniquement) : http://127.0.0.1:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
