"""Client léger pour l'API REST Render (https://api.render.com/v1).

ATTENTION : partiellement validé contre un vrai compte Render seulement (cf. Phase 0 de
docs/FLEET_PROVISIONING_PLAN.md). Premier essai réel (2026-07-14) : POST /postgres a échoué
avec `{"message":"version is required"}` — corrigé, avec vérification du schéma OpenAPI réel
(https://api-docs.render.com/v1.0/openapi/render-public-api-1.json) pour TOUS les endpoints
utilisés ci-dessous plutôt que de deviner champ par champ à chaque nouvel échec. Plusieurs
autres écarts entre la doc publique lue initialement et le schéma réel ont été trouvés et
corrigés au même moment (cf. commentaires inline : `runtime` vs `env`, enveloppes de réponse
`service`/`deploy`...). Le comportement exact de l'attente du certificat TLS sur un domaine
personnalisé (`add_custom_domain`) reste, lui, non vérifié — pas encore testé en pratique.
Toujours tester avec `provision_client.py --dry-run` d'abord, puis sur une instance de test
(Phase 4 du plan), jamais directement sur un client réel.
"""
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

RENDER_API_BASE = "https://api.render.com/v1"
RENDER_API_KEY = os.getenv("RENDER_API_KEY")

DEFAULT_REGION = "frankfurt"  # Cohérent avec render.yaml existant (UE, RGPD)

# Valeurs exactes du schéma postgresVersion de l'API Render (vérifiées sur le schéma OpenAPI
# réel le 2026-07-14, pas devinées) — toujours des chaînes, jamais des entiers.
SUPPORTED_POSTGRES_VERSIONS = ("11", "12", "13", "14", "15", "16", "17", "18")
# Alignée sur docker-compose.yml et .github/workflows/ci.yml (image pgvector/pgvector:pg18,
# déjà la version validée partout ailleurs dans le projet) et confirmée par la doc Render
# (render.com/docs/postgresql-extensions) : pgvector supporté sans restriction de version
# maximale sur Postgres 13+.
DEFAULT_POSTGRES_VERSION = "18"


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


def create_postgres(
    *, name: str, owner_id: str, plan: str, database_name: str, database_user: str,
    version: str = DEFAULT_POSTGRES_VERSION, region: str = DEFAULT_REGION,
) -> dict:
    """Plan JAMAIS 'free' pour une instance client — décision actée le 2026-07-09
    (docs/FLEET_PROVISIONING_PLAN.md, Phase 0) : le plan gratuit Render n'offre aucun
    backup automatique. `plan` doit être un plan payant (ex: 'starter').

    `version` est REQUIS par l'API Render (champ absent avant le 2026-07-14, premier échec
    réel : `{"message":"version is required"}`) — cf. SUPPORTED_POSTGRES_VERSIONS ci-dessus."""
    if plan.lower() == "free":
        raise RenderAPIError("Plan Postgres 'free' refusé pour une instance client — aucun backup automatique sur ce plan.")
    if version not in SUPPORTED_POSTGRES_VERSIONS:
        raise RenderAPIError(
            f"Version PostgreSQL '{version}' non supportée par l'API Render. "
            f"Valeurs acceptées : {', '.join(SUPPORTED_POSTGRES_VERSIONS)}."
        )
    return _request("POST", "/postgres", json={
        "name": name,
        "ownerId": owner_id,
        "plan": plan,
        "region": region,
        "databaseName": database_name,
        "databaseUser": database_user,
        "version": version,
    })


def get_postgres_connection_info(postgres_id: str) -> dict:
    return _request("GET", f"/postgres/{postgres_id}/connection-info")


def create_web_service(
    *, name: str, owner_id: str, repo: str, branch: str, root_dir: str,
    dockerfile_path: str, env_vars: dict[str, str], plan: str, health_check_path: str = "/",
    region: str = DEFAULT_REGION,
) -> dict:
    """`serviceDetails.runtime` (pas `env`, déprécié côté API malgré son nom trompeur) et
    `serviceDetails.envSpecificDetails.dockerfilePath` (pas `dockerDetails` à la racine de
    serviceDetails) — vérifié sur le schéma OpenAPI réel (webServiceDetailsPOST.required =
    ["runtime"], envSpecificDetailsPOST = oneOf[dockerDetailsPOST, nativeEnvironmentDetailsPOST]),
    pas deviné depuis la doc publique."""
    response = _request("POST", "/services", json={
        "type": "web_service",
        "name": name,
        "ownerId": owner_id,
        "repo": repo,
        "branch": branch,
        "rootDir": root_dir,
        "envVars": [{"key": k, "value": v} for k, v in env_vars.items()],
        "serviceDetails": {
            "runtime": "docker",
            "envSpecificDetails": {"dockerfilePath": dockerfile_path},
            "plan": plan,
            "region": region,
            "healthCheckPath": health_check_path,
        },
    })
    # POST /services renvoie {"service": {...}, "deployId": "..."}, pas le service
    # directement (schéma de réponse `serviceAndDeploy`) — on ne renvoie que `service` pour
    # que les appelants puissent lire `.["id"]`/`.["serviceDetails"]` sans connaître cette
    # enveloppe. `backend_service["id"]` aurait levé un KeyError sans ce déballage.
    return response["service"]


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
    # GET .../deploys renvoie [{"cursor": ..., "deploy": {...}}], pas les deploys
    # directement (schéma de réponse `deployList` -> items `deployWithCursor`) — sans ce
    # déballage, deploy.get("status") ne trouve jamais rien et wait_for_deploy_live()
    # attend le timeout complet (900s) à chaque appel, y compris sur un déploiement réussi.
    deploys = _request("GET", f"/services/{service_id}/deploys?limit=1")
    return deploys[0]["deploy"] if deploys else None


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
        if status in {"build_failed", "update_failed", "canceled", "deactivated", "pre_deploy_failed"}:
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
