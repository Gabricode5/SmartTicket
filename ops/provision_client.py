#!/usr/bin/env python3
"""Provisionne une instance SmartTicket complète pour un nouveau client (Postgres + backend
+ frontend Render), enregistre l'instance dans ops/instances.db.

Usage :
    python provision_client.py --name "Acme Corp" --slug acme-corp --postgres-plan starter
    python provision_client.py --name "Acme Corp" --slug acme-corp --postgres-plan starter --dry-run

Prérequis (cf. docs/FLEET_PROVISIONING_PLAN.md, Phase 0) :
    - RENDER_API_KEY exporté dans l'environnement
    - MISTRAL_API_KEY / BREVO_API_KEY exportés (secrets partagés entre clients pour l'instant,
      cf. décision Phase 0 — à revoir une fois le métering par instance en place)
    - Si --domain est fourni : le domaine doit déjà exister et pointer vers Render (wildcard
      DNS), cf. Phase 0. Sans --domain, l'instance reste accessible via son URL *.onrender.com.

ATTENTION : non testé contre un vrai compte Render (cf. render_client.py). Toujours lancer avec
--dry-run d'abord, puis sur une instance de test jetable avant tout client réel (Phase 4 du
plan). L'amorçage admin ci-dessous génère un mot de passe temporaire affiché une seule fois
en console (pas écrit sur disque, pas loggé) — la page /setup?key=... décrite en Phase 2 du
plan pour éliminer ce mot de passe temporaire n'est pas encore construite (hors scope de
cette étape, uniquement les scripts CLI + la table instances).
"""
import argparse
import secrets
import sys

if hasattr(sys.stdout, "reconfigure"):
    # Console Windows en cp1252 par défaut : sans ça, les accents s'affichent en '?'
    # (pas une erreur, juste illisible) — la sortie de ces scripts contient du français.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import db
import render_client as render

DEFAULT_REPO = "https://github.com/Gabricode5/SmartTicket"
DEFAULT_BRANCH = "main"


def generate_secret(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def build_urls(slug: str, domain: str | None) -> tuple[str, str]:
    """Retourne (backend_url, frontend_url) attendues. Si --domain n'est pas fourni, ces
    URLs *.onrender.com ne sont connues qu'après création des services — cette fonction
    n'est alors utilisée que pour construire le custom domain, pas les URLs finales."""
    if domain:
        return f"https://{slug}-api.{domain}", f"https://{slug}.{domain}"
    return "", ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="Nom lisible du client (ex: 'Acme Corp')")
    parser.add_argument("--slug", required=True, help="Identifiant court, sans espaces (ex: acme-corp)")
    parser.add_argument("--postgres-plan", required=True, help="Plan Postgres Render (JAMAIS 'free' — aucun backup sur ce plan)")
    parser.add_argument("--web-plan", default="starter", help="Plan Render pour les services web (défaut: starter)")
    parser.add_argument("--domain", default=None, help="Suffixe de domaine (ex: smartticket.fr) — sans domaine, l'instance reste sur *.onrender.com")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"Repo GitHub à déployer (défaut: {DEFAULT_REPO})")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help=f"Branche à déployer (défaut: {DEFAULT_BRANCH})")
    parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait fait sans rien créer")
    args = parser.parse_args()

    db.init_db()

    if db.slug_exists(args.slug):
        print(f"Erreur : le slug '{args.slug}' existe déjà dans ops/instances.db. Refus de dupliquer les ressources.", file=sys.stderr)
        return 1

    if args.postgres_plan.lower() == "free":
        print("Erreur : --postgres-plan free refusé pour une instance client (pas de backup automatique).", file=sys.stderr)
        return 1

    backend_name = f"smartticket-{args.slug}-backend"
    frontend_name = f"smartticket-{args.slug}-frontend"
    db_name = f"smartticket-{args.slug}-postgres"

    secret_key = generate_secret()
    admin_setup_key = generate_secret()
    vendor_key = generate_secret()
    temp_admin_password = generate_secret(12)

    expected_backend_url, expected_frontend_url = build_urls(args.slug, args.domain)

    if args.dry_run:
        print("--- DRY RUN : rien ne sera créé ---")
        print(f"Postgres      : {db_name} (plan={args.postgres_plan})")
        print(f"Backend       : {backend_name} (plan={args.web_plan}) — repo={args.repo}@{args.branch}, rootDir=backend")
        print(f"Frontend      : {frontend_name} (plan={args.web_plan}) — repo={args.repo}@{args.branch}, rootDir=frontend")
        if args.domain:
            print(f"Domaine       : {expected_frontend_url} (frontend), {expected_backend_url} (backend, si applicable)")
        else:
            print("Domaine       : aucun — URLs *.onrender.com par défaut")
        print("Secrets générés (non affichés en dry-run — regénérés à chaque exécution réelle)")
        return 0

    owner_id = render.get_owner_id()

    print(f"Création de la base Postgres '{db_name}'...")
    postgres = render.create_postgres(
        name=db_name, owner_id=owner_id, plan=args.postgres_plan,
        database_name=args.slug.replace("-", "_"), database_user="admin",
    )
    postgres_id = postgres["id"]

    print("Attente de la disponibilité de la base...")
    connection_info = render.get_postgres_connection_info(postgres_id)
    database_url = connection_info.get("internalConnectionString") or connection_info.get("externalConnectionString")
    if not database_url:
        print("Erreur : impossible de récupérer la chaîne de connexion de la base Postgres.", file=sys.stderr)
        return 1

    cors_origins = expected_frontend_url or "https://placeholder.onrender.com"

    backend_env = {
        "DATABASE_URL": database_url,
        "SECRET_KEY": secret_key,
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "CORS_ORIGINS": cors_origins,
        "ADMIN_SETUP_KEY": admin_setup_key,
        "VENDOR_KEY": vendor_key,
        "ADMIN_EMAIL": f"admin@{args.slug}.smartticket.local",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": temp_admin_password,
        "MISTRAL_API_KEY": _shared_secret("MISTRAL_API_KEY"),
        "EMBED_MODEL": "mistral-embed",
        "BREVO_API_KEY": _shared_secret("BREVO_API_KEY", required=False),
    }

    print(f"Création du service backend '{backend_name}'...")
    backend_service = render.create_web_service(
        name=backend_name, owner_id=owner_id, repo=args.repo, branch=args.branch,
        root_dir="backend", dockerfile_path="./Dockerfile", env_vars=backend_env,
        plan=args.web_plan, health_check_path="/",
    )
    backend_service_id = backend_service["id"]

    print("Attente du premier déploiement backend (peut prendre plusieurs minutes)...")
    if not render.wait_for_deploy_live(backend_service_id):
        print("Attention : le backend n'est pas encore 'live' après le délai d'attente — vérifie manuellement sur Render.", file=sys.stderr)

    backend_actual_url = expected_backend_url or backend_service.get("serviceDetails", {}).get("url", "")

    frontend_env = {
        "NEXT_PUBLIC_API_URL": backend_actual_url,
    }

    print(f"Création du service frontend '{frontend_name}'...")
    frontend_service = render.create_web_service(
        name=frontend_name, owner_id=owner_id, repo=args.repo, branch=args.branch,
        root_dir="frontend", dockerfile_path="./Dockerfile", env_vars=frontend_env,
        plan=args.web_plan,
    )
    frontend_service_id = frontend_service["id"]

    print("Attente du premier déploiement frontend...")
    if not render.wait_for_deploy_live(frontend_service_id):
        print("Attention : le frontend n'est pas encore 'live' après le délai d'attente — vérifie manuellement sur Render.", file=sys.stderr)

    frontend_actual_url = expected_frontend_url or frontend_service.get("serviceDetails", {}).get("url", "")

    if args.domain:
        print(f"Attachement du domaine personnalisé {frontend_actual_url}...")
        render.add_custom_domain(frontend_service_id, f"{args.slug}.{args.domain}")
        # CORS_ORIGINS a déjà été posé sur le domaine final ci-dessus (étape backend) —
        # rien à corriger ici, contrairement au cas sans --domain juste en dessous.
    elif not expected_frontend_url:
        # Sans --domain, l'URL finale du frontend n'était pas connue lors de la création du
        # backend (CORS_ORIGINS pointait vers un placeholder) — on corrige maintenant.
        print("Correction de CORS_ORIGINS avec l'URL *.onrender.com réelle du frontend...")
        backend_env["CORS_ORIGINS"] = frontend_actual_url
        render.set_env_vars(backend_service_id, backend_env)

    db.insert_instance(
        client_name=args.name, slug=args.slug,
        render_backend_service_id=backend_service_id,
        render_frontend_service_id=frontend_service_id,
        render_database_id=postgres_id,
        backend_url=backend_actual_url, frontend_url=frontend_actual_url,
        subdomain=f"{args.slug}.{args.domain}" if args.domain else None,
        vendor_key=vendor_key, admin_setup_key=admin_setup_key,
        statut="active",
    )

    print("\n--- Instance provisionnée ---")
    print(f"Client        : {args.name} ({args.slug})")
    print(f"Frontend      : {frontend_actual_url}")
    print(f"Backend       : {backend_actual_url}")
    print(f"VENDOR_KEY    : {vendor_key}  (à conserver en lieu sûr — coupe-circuit d'abonnement)")
    print(f"Admin login   : admin@{args.slug}.smartticket.local")
    print(f"Admin mdp     : {temp_admin_password}  (temporaire — à communiquer au client de manière sécurisée puis à faire changer immédiatement, la page /setup sans mot de passe n'est pas encore construite)")
    return 0


def _shared_secret(env_var: str, required: bool = True) -> str:
    import os
    value = os.getenv(env_var)
    if not value and required:
        raise RuntimeError(f"{env_var} manquante dans l'environnement du script (secret partagé entre instances, cf. Phase 0 du plan).")
    return value or ""


if __name__ == "__main__":
    sys.exit(main())
