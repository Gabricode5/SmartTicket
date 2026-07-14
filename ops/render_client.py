"""Client léger pour l'API REST Render (https://api.render.com/v1).

ATTENTION : non validé contre un vrai compte Render (cf. Phase 0 de docs/FLEET_PROVISIONING_PLAN.md,
case encore non cochée) — les noms d'endpoints et la forme exacte des payloads ci-dessous
sont basés sur la documentation publique Render au moment de l'écriture, mais l'API évolue
et certains détails (nommage précis des champs `serviceDetails`, comportement exact de
l'attente du certificat TLS...) doivent être confirmés avec un premier appel réel avant
de faire confiance à ce module sur un client payant. Toujours tester avec
`provision_client.py --dry-run` d'abord, puis sur une instance de test (Phase 4 du plan),
jamais directement sur un client réel.
"""
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

RENDER_API_BASE = "https://api.render.com/v1"
RENDER_API_KEY = os.getenv("RENDER_API_KEY")

DEFAULT_REGION = "frankfurt"  # Cohérent avec render.yaml existant (UE, RGPD)


class RenderAPIError(RuntimeError):
    pass


def _require_api_key() -> str:
    if not RENDER_API_KEY:
        raise RenderAPIError(
            "RENDER_API_KEY manquante. Génère un token dans Render → Account Settings → "
            "API Keys, puis exporte-le : export RENDER_API_KEY=..."
        )
    return RENDER_API_KEY


def _request(method: str, path: str, **kwargs) -> dict:
    api_key = _require_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if "json" in kwargs:
        headers["Content-Type"] = "application/json"
    response = requests.request(method, f"{RENDER_API_BASE}{path}", headers=headers, timeout=30, **kwargs)
    if not response.ok:
        raise RenderAPIError(f"{method} {path} -> {response.status_code}: {response.text}")
    return response.json() if response.content else {}


def get_owner_id() -> str:
    """Résout l'ownerId du premier workspace disponible sur ce token. Si le compte a
    plusieurs workspaces, ADAPTER cette fonction (ex: filtrer par nom) plutôt que
    d'utiliser silencieusement le premier venu."""
    owners = _request("GET", "/owners")
    if not owners:
        raise RenderAPIError("Aucun owner/workspace trouvé sur ce token Render.")
    return owners[0]["owner"]["id"]


def create_postgres(*, name: str, owner_id: str, plan: str, database_name: str, database_user: str, region: str = DEFAULT_REGION) -> dict:
    """Plan JAMAIS 'free' pour une instance client — décision actée le 2026-07-09
    (docs/FLEET_PROVISIONING_PLAN.md, Phase 0) : le plan gratuit Render n'offre aucun
    backup automatique. `plan` doit être un plan payant (ex: 'starter')."""
    if plan.lower() == "free":
        raise RenderAPIError("Plan Postgres 'free' refusé pour une instance client — aucun backup automatique sur ce plan.")
    return _request("POST", "/postgres", json={
        "name": name,
        "ownerId": owner_id,
        "plan": plan,
        "region": region,
        "databaseName": database_name,
        "databaseUser": database_user,
    })


def get_postgres_connection_info(postgres_id: str) -> dict:
    return _request("GET", f"/postgres/{postgres_id}/connection-info")


def create_web_service(
    *, name: str, owner_id: str, repo: str, branch: str, root_dir: str,
    dockerfile_path: str, env_vars: dict[str, str], plan: str, health_check_path: str = "/",
    region: str = DEFAULT_REGION,
) -> dict:
    return _request("POST", "/services", json={
        "type": "web_service",
        "name": name,
        "ownerId": owner_id,
        "repo": repo,
        "branch": branch,
        "rootDir": root_dir,
        "envVars": [{"key": k, "value": v} for k, v in env_vars.items()],
        "serviceDetails": {
            "env": "docker",
            "dockerDetails": {"dockerfilePath": dockerfile_path},
            "plan": plan,
            "region": region,
            "healthCheckPath": health_check_path,
        },
    })


def set_env_vars(service_id: str, env_vars: dict[str, str]) -> dict:
    """Remplace intégralement les env vars du service (l'API Render fait un PUT complet,
    pas un patch incrémental) — toujours repartir des env vars déjà connues si on veut en
    ajouter sans écraser le reste."""
    return _request("PUT", f"/services/{service_id}/env-vars", json=[{"key": k, "value": v} for k, v in env_vars.items()])


def add_custom_domain(service_id: str, domain: str) -> dict:
    return _request("POST", f"/services/{service_id}/custom-domains", json={"name": domain})


def get_service(service_id: str) -> dict:
    return _request("GET", f"/services/{service_id}")


def get_latest_deploy(service_id: str) -> dict | None:
    deploys = _request("GET", f"/services/{service_id}/deploys?limit=1")
    return deploys[0] if deploys else None


def trigger_deploy(service_id: str) -> dict:
    return _request("POST", f"/services/{service_id}/deploys", json={})


def delete_service(service_id: str) -> None:
    _request("DELETE", f"/services/{service_id}")


def delete_postgres(postgres_id: str) -> None:
    _request("DELETE", f"/postgres/{postgres_id}")


def wait_for_deploy_live(service_id: str, *, timeout_seconds: int = 900, poll_interval_seconds: int = 15) -> bool:
    """Poll jusqu'à ce que le dernier déploiement du service passe à 'live', ou jusqu'au
    timeout. Retourne False sans lever d'exception en cas de timeout — laisse l'appelant
    décider quoi faire (le service peut toujours devenir live juste après)."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        deploy = get_latest_deploy(service_id)
        status = deploy.get("status") if deploy else None
        if status == "live":
            return True
        if status in {"build_failed", "update_failed", "canceled", "deactivated"}:
            raise RenderAPIError(f"Déploiement du service {service_id} en échec : statut '{status}'")
        time.sleep(poll_interval_seconds)
    return False


def delete_resources(resources: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Supprime une liste de ressources Render — best-effort, une suppression qui échoue
    n'empêche pas de tenter les suivantes (même logique que delete_client.py, factorisée ici
    pour que provision_client.py::_rollback() la réutilise telle quelle plutôt que de la
    réécrire). `resources` est une liste de tuples (label, type, id) où type vaut 'service'
    ou 'postgres', DANS L'ORDRE où elles doivent être supprimées (à l'appelant de les passer
    déjà en ordre inverse de création si c'est un rollback). Ne lève jamais : retourne la
    sous-liste des entrées qui n'ont PAS pu être supprimées (mêmes tuples, même ordre), pour
    que l'appelant les logue, les affiche ou les persiste — un échec de suppression ne doit
    jamais être avalé silencieusement."""
    failed: list[tuple[str, str, str]] = []
    for label, resource_type, resource_id in resources:
        try:
            if resource_type == "postgres":
                delete_postgres(resource_id)
            else:
                delete_service(resource_id)
        except RenderAPIError as exc:
            logger.error("Échec de suppression (%s, id=%s) : %s", label, resource_id, exc)
            failed.append((label, resource_type, resource_id))
    return failed
