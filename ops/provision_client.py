#!/usr/bin/env python3
"""Provisionne une instance SmartTicket complète pour un nouveau client (Postgres + backend
+ frontend Render), enregistre l'instance dans ops/instances.db.

Usage :
    python provision_client.py --name "Acme Corp" --slug acme-corp --admin-email admin@acme.com --postgres-plan starter
    python provision_client.py --name "Acme Corp" --slug acme-corp --admin-email admin@acme.com --postgres-plan starter --dry-run

Prérequis (cf. docs/FLEET_PROVISIONING_PLAN.md, Phase 0) :
    - RENDER_API_KEY exporté dans l'environnement
    - MISTRAL_API_KEY / BREVO_API_KEY exportés (secrets partagés entre clients pour l'instant,
      cf. décision Phase 0 — à revoir une fois le métering par instance en place)
    - Si --domain est fourni : le domaine doit déjà exister et pointer vers Render (wildcard
      DNS), cf. Phase 0. Sans --domain, l'instance reste accessible via son URL *.onrender.com.

ATTENTION : plusieurs essais réels contre un vrai compte Render effectués le 2026-07-14 (cf.
render_client.py pour le détail des écarts trouvés et corrigés avec le schéma OpenAPI réel de
Render). Confirmés fonctionner en pratique : création de la base Postgres, rollback sur échec
partiel, POST /v1/setup (amorçage du compte admin par token). Bug trouvé et corrigé sur cette
même série d'essais : sans --domain, le frontend recevait NEXT_PUBLIC_API_URL vide à son
premier build (Next.js bake les rewrites de next.config.ts au build, jamais au runtime) —
build_urls() prédit maintenant les URLs *.onrender.com par avance au lieu de les découvrir
après coup — cf. frontend/scripts/verify-production-build.mjs (lancé en CI juste après
`next build`), qui fait maintenant échouer explicitement tout build où le rewrite /api/*
retomberait sur ce fallback localhost. L'attachement d'un domaine personnalisé (--domain),
lui, reste non testé en conditions réelles (en particulier l'attente du certificat TLS).
Toujours lancer avec
--dry-run d'abord, puis sur une instance de test jetable avant tout client réel (Phase 4 du
plan).

La logique métier vit dans provision() — une fonction pure (pas d'input(), pas de print()
comme moyen de retour, uniquement du logging + une valeur de retour) appelable telle quelle
par un futur déclencheur automatisé (ex: webhook de paiement). main() n'est qu'un mince
wrapper CLI : parse les arguments, gère le --dry-run (qui n'appelle jamais provision(), pour
ne jamais faire de vrai appel réseau), affiche le résultat pour un humain.
"""
import argparse
import logging
import secrets
import sys
from dataclasses import dataclass

if hasattr(sys.stdout, "reconfigure"):
    # Console Windows en cp1252 par défaut : sans ça, les accents s'affichent en '?'
    # (pas une erreur, juste illisible) — la sortie de ces scripts contient du français.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import db
import notify
import render_client as render

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_REPO = "https://github.com/Gabricode5/SmartTicket"
DEFAULT_BRANCH = "main"


@dataclass
class ProvisionResult:
    slug: str
    status: str  # "active" | "failed"
    backend_url: str = ""
    frontend_url: str = ""
    vendor_key: str = ""
    setup_url: str = ""  # lien /setup?token=... à usage unique — aucun mot de passe en clair
    welcome_email_sent: bool = False
    error: str | None = None


def generate_secret(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def backend_service_name(slug: str) -> str:
    return f"smartticket-{slug}-backend"


def frontend_service_name(slug: str) -> str:
    return f"smartticket-{slug}-frontend"


def build_urls(slug: str, domain: str | None) -> tuple[str, str]:
    """Retourne (backend_url, frontend_url) — TOUJOURS prédites à l'avance, jamais
    découvertes après coup depuis la réponse de l'API Render. Avec --domain, ce sont les
    URLs du domaine personnalisé (posé plus tard via add_custom_domain). Sans --domain,
    l'URL *.onrender.com est déterministe à partir du nom de service que NOUS choisissons
    (https://{nom}.onrender.com — confirmé par la doc Render, pas besoin d'attendre une
    réponse d'API pour la connaître).

    Bug trouvé le 2026-07-14 lors d'un provisioning réel : cette fonction renvoyait ("", "")
    sans --domain, sur l'hypothèse (fausse) que l'URL n'était connue qu'après création. Le
    frontend recevait donc NEXT_PUBLIC_API_URL vide à son PREMIER build — et Next.js bake
    les rewrites de next.config.ts au build, pas au runtime (confirmé : rewrites() n'est
    réévalué ni par `next start` ni par un redeploy à chaud, seul un nouveau build compte) —
    donc le fallback "http://localhost:8000" restait figé dans l'image, et tous les appels
    /api/* du frontend déployé échouaient en 404 (proxy Next.js vers un localhost qui
    n'écoute rien dans le conteneur frontend)."""
    if domain:
        return f"https://{slug}-api.{domain}", f"https://{slug}.{domain}"
    return f"https://{backend_service_name(slug)}.onrender.com", f"https://{frontend_service_name(slug)}.onrender.com"


def _shared_secret(env_var: str, required: bool = True) -> str:
    import os
    value = os.getenv(env_var)
    if not value and required:
        raise RuntimeError(f"{env_var} manquante dans l'environnement du script (secret partagé entre instances, cf. Phase 0 du plan).")
    return value or ""


def _rollback(slug: str, created_resources: list[tuple[str, str, str]], *, error: str) -> ProvisionResult:
    """Défait au mieux les ressources Render déjà créées avant l'échec, en ORDRE INVERSE de
    création — dernière créée, première supprimée (les dépendances éventuelles entre
    ressources, ex. domaine custom posé sur le frontend, se défont dans le bon sens).
    Réutilise render_client.delete_resources() : même logique best-effort que
    delete_client.py (continue même si une suppression échoue), pas réimplémentée ici.

    Politique de slug après échec (délibérée, pas un détail) :
      - Rollback COMPLET (toutes les ressources supprimées) → la ligne instances.db est
        retirée : le slug redevient libre, un retry derrière est sûr (aucune ressource
        Render ne subsiste sous ce nom, donc aucun risque de collision).
      - Rollback INCOMPLET (au moins une ressource survit) → la ligne est marquée
        statut='failed' et CONSERVÉE (avec les IDs orphelins dans `notes`) : le slug reste
        donc "brûlé" (db.slug_exists() continue de le bloquer) tant qu'un humain n'a pas
        nettoyé manuellement sur le dashboard Render et supprimé la ligne à la main. Le
        laisser réutilisable ici serait dangereux : retenter provisionnerait de nouvelles
        ressources avec des noms Render potentiellement déjà pris par les orphelines
        (smartticket-{slug}-backend, etc.), ou pire, laisserait deux jeux de ressources
        actifs sous des identités qui se ressemblent sans que personne ne s'en aperçoive.
    """
    logger.warning("Rollback de '%s' : suppression de %d ressource(s) déjà créée(s)...", slug, len(created_resources))
    failed = render.delete_resources(list(reversed(created_resources)))

    if not failed:
        db.delete_instance_row(slug)
        logger.info("Rollback de '%s' terminé : ressources supprimées, slug libéré pour un nouvel essai.", slug)
        return ProvisionResult(slug=slug, status="failed", error=error)

    orphans = "; ".join(f"{label} (id={resource_id})" for label, _, resource_id in failed)
    rollback_error = (
        f"{error} — ROLLBACK INCOMPLET : {len(failed)} ressource(s) Render n'ont pas pu être "
        f"supprimées et restent probablement facturées : {orphans}. Nettoyage manuel requis "
        f"sur le dashboard Render, puis suppression de la ligne '{slug}' dans instances.db. "
        f"Le slug '{slug}' reste réservé (statut 'failed') tant que ce nettoyage n'est pas fait "
        f"— ne PAS relancer le provisioning avec le même slug avant."
    )
    logger.error(rollback_error)
    db.update_instance(slug, statut="failed", notes=orphans)
    return ProvisionResult(slug=slug, status="failed", error=rollback_error)


def provision(
    *, client_name: str, slug: str, postgres_plan: str, admin_email: str,
    domain: str | None = None, web_plan: str = "starter",
    postgres_version: str = render.DEFAULT_POSTGRES_VERSION,
    repo: str = DEFAULT_REPO, branch: str = DEFAULT_BRANCH,
) -> ProvisionResult:
    """Crée Postgres + backend + frontend Render pour un nouveau client et enregistre
    l'instance dans ops/instances.db. Ne fait aucun appel réseau tant que l'idempotence et
    la validité du plan Postgres n'ont pas été vérifiées.

    Le slug est réservé dans instances.db (statut 'provisioning') AVANT le moindre appel
    Render, et chaque ID de ressource y est persisté dès sa création (pas seulement à la
    fin) : même un crash non rattrapé par le except ci-dessous (process tué, coupure
    réseau irrécupérable...) laisse une trace exploitable pour un nettoyage manuel. En cas
    d'échec intercepté, cf. _rollback() ci-dessus pour la suite."""
    db.init_db()

    if db.slug_exists(slug):
        return ProvisionResult(slug=slug, status="failed", error=f"Le slug '{slug}' existe déjà dans ops/instances.db.")

    backend_name = backend_service_name(slug)
    frontend_name = frontend_service_name(slug)
    db_name = f"smartticket-{slug}-postgres"

    secret_key = generate_secret()
    vendor_key = generate_secret()
    admin_setup_token = generate_secret()  # jamais un mot de passe : cf. POST /v1/setup côté backend

    # Toujours non vides désormais (cf. build_urls()) — utilisées directement pour
    # CORS_ORIGINS et NEXT_PUBLIC_API_URL dès la création des services, sans avoir besoin
    # d'un deuxième déploiement correctif après coup.
    backend_url, frontend_url = build_urls(slug, domain)

    db.insert_instance(client_name=client_name, slug=slug, vendor_key=vendor_key, statut="provisioning")

    # (label, type, id) dans l'ORDRE de création — relu à l'envers par _rollback() en cas
    # d'échec plus bas.
    created_resources: list[tuple[str, str, str]] = []

    try:
        owner_id = render.get_owner_id()

        logger.info("Création de la base Postgres '%s'...", db_name)
        postgres = render.create_postgres(
            name=db_name, owner_id=owner_id, plan=postgres_plan, version=postgres_version,
            database_name=slug.replace("-", "_"), database_user="admin",
        )
        postgres_id = postgres["id"]
        created_resources.append(("base Postgres", "postgres", postgres_id))
        db.update_instance(slug, render_database_id=postgres_id)

        logger.info("Attente de la disponibilité de la base...")
        # VRAI polling sur le statut ('creating' -> 'available') avant connection-info —
        # sans ça, get_postgres_connection_info() peut répondre 404 alors même que l'ID est
        # valide : la base existe mais Render n'a pas fini de la provisionner (race
        # condition confirmée en conditions réelles le 2026-07-15, ~400ms entre la création
        # et le premier appel connection-info ont suffi à la déclencher).
        if not render.wait_for_postgres_available(postgres_id):
            raise RuntimeError(f"La base Postgres {postgres_id} n'est toujours pas 'available' après le délai d'attente.")

        connection_info = render.get_postgres_connection_info(postgres_id)
        database_url = connection_info.get("internalConnectionString") or connection_info.get("externalConnectionString")
        if not database_url:
            raise RuntimeError("Impossible de récupérer la chaîne de connexion de la base Postgres.")

        backend_env = {
            "DATABASE_URL": database_url,
            "SECRET_KEY": secret_key,
            "ALGORITHM": "HS256",
            "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
            "CORS_ORIGINS": frontend_url,
            "VENDOR_KEY": vendor_key,
            "ADMIN_EMAIL": admin_email,
            "ADMIN_USERNAME": "admin",
            # Volontairement PAS d'ADMIN_PASSWORD : main.py::run_migrations crée le compte avec
            # un mot de passe aléatoire inconnu de tous et ce token, en attente de POST /v1/setup.
            # Volontairement PAS d'ADMIN_SETUP_KEY non plus : cette variable réactiverait la
            # route de secours POST /v1/setup-admin (inerte tant qu'elle est absente, cf.
            # backend/routers/auth.py) sur une instance client de production — cf. décision
            # documentée dans docs/FLEET_PROVISIONING_PLAN.md.
            "ADMIN_SETUP_TOKEN": admin_setup_token,
            "MISTRAL_API_KEY": _shared_secret("MISTRAL_API_KEY"),
            "EMBED_MODEL": "mistral-embed",
            "BREVO_API_KEY": _shared_secret("BREVO_API_KEY", required=False),
        }

        logger.info("Création du service backend '%s'...", backend_name)
        backend_service = render.create_web_service(
            name=backend_name, owner_id=owner_id, repo=repo, branch=branch,
            root_dir="backend", dockerfile_path="./Dockerfile", env_vars=backend_env,
            plan=web_plan, health_check_path="/",
        )
        backend_service_id = backend_service["id"]
        created_resources.append(("service backend", "service", backend_service_id))
        db.update_instance(slug, render_backend_service_id=backend_service_id)

        logger.info("Attente du premier déploiement backend (peut prendre plusieurs minutes)...")
        if not render.wait_for_deploy_live(backend_service_id):
            logger.warning("Le backend n'est pas encore 'live' après le délai d'attente — vérifie manuellement sur Render.")

        # Contrôle de cohérence diagnostique (pas correctif) : l'URL *.onrender.com est
        # censée être déterministe à partir du nom qu'on a choisi (cf. build_urls()), mais
        # ce nom n'est garanti unique QUE dans notre workspace — une collision globale sur
        # Render resterait possible en théorie. Si l'API renvoie une URL différente de celle
        # prédite, NEXT_PUBLIC_API_URL/CORS_ORIGINS seront quand même posées avec la valeur
        # prédite (celle qu'on a demandée) ; ce log est le seul filet pour repérer une
        # divergence avant qu'elle ne se traduise en 404 silencieux côté client.
        backend_reported_url = backend_service.get("serviceDetails", {}).get("url", "")
        if backend_reported_url and backend_reported_url != backend_url:
            logger.warning(
                "URL backend réelle (%s) différente de l'URL prédite (%s) — probable "
                "collision de nom *.onrender.com. NEXT_PUBLIC_API_URL/CORS_ORIGINS utilisent "
                "la valeur prédite : vérifier manuellement si le frontend ne joint pas le backend.",
                backend_reported_url, backend_url,
            )

        frontend_env = {
            "NEXT_PUBLIC_API_URL": backend_url,
        }

        logger.info("Création du service frontend '%s'...", frontend_name)
        frontend_service = render.create_web_service(
            name=frontend_name, owner_id=owner_id, repo=repo, branch=branch,
            root_dir="frontend", dockerfile_path="./Dockerfile", env_vars=frontend_env,
            plan=web_plan,
        )
        frontend_service_id = frontend_service["id"]
        created_resources.append(("service frontend", "service", frontend_service_id))
        db.update_instance(slug, render_frontend_service_id=frontend_service_id)

        logger.info("Attente du premier déploiement frontend...")
        if not render.wait_for_deploy_live(frontend_service_id):
            logger.warning("Le frontend n'est pas encore 'live' après le délai d'attente — vérifie manuellement sur Render.")

        # Même contrôle diagnostique que côté backend ci-dessus.
        frontend_reported_url = frontend_service.get("serviceDetails", {}).get("url", "")
        if frontend_reported_url and frontend_reported_url != frontend_url:
            logger.warning(
                "URL frontend réelle (%s) différente de l'URL prédite (%s) — probable "
                "collision de nom *.onrender.com. Le lien de setup utilisera quand même la "
                "valeur prédite : vérifier manuellement s'il ne fonctionne pas.",
                frontend_reported_url, frontend_url,
            )

        if domain:
            logger.info("Attachement du domaine personnalisé %s...", frontend_url)
            render.add_custom_domain(frontend_service_id, f"{slug}.{domain}")

        setup_url = f"{frontend_url}/setup?token={admin_setup_token}"

    except Exception as exc:
        logger.error(
            "Échec du provisioning de '%s' après création de %d ressource(s) : %s",
            slug, len(created_resources), exc, exc_info=True,
        )
        return _rollback(slug, created_resources, error=str(exc))

    db.update_instance(
        slug,
        backend_url=backend_url, frontend_url=frontend_url,
        subdomain=f"{slug}.{domain}" if domain else None,
        statut="active",
    )

    logger.info("Envoi de l'email de bienvenue à %s...", admin_email)
    welcome_email_sent = notify.send_welcome_email(
        admin_email=admin_email, client_name=client_name, setup_url=setup_url,
    )

    return ProvisionResult(
        slug=slug, status="active",
        backend_url=backend_url, frontend_url=frontend_url,
        vendor_key=vendor_key, setup_url=setup_url, welcome_email_sent=welcome_email_sent,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="Nom lisible du client (ex: 'Acme Corp')")
    parser.add_argument("--slug", required=True, help="Identifiant court, sans espaces (ex: acme-corp)")
    parser.add_argument("--admin-email", required=True, help="Email du compte admin du client (recevra le lien de setup)")
    parser.add_argument("--postgres-plan", required=True, help="Plan Postgres Render (JAMAIS 'free' — aucun backup sur ce plan)")
    parser.add_argument(
        "--postgres-version", default=render.DEFAULT_POSTGRES_VERSION,
        choices=render.SUPPORTED_POSTGRES_VERSIONS,
        help=f"Version majeure de PostgreSQL (défaut: {render.DEFAULT_POSTGRES_VERSION}, "
             "alignée sur docker-compose.yml/CI — pgvector supporté sans restriction sur "
             "Postgres 13+ côté Render)",
    )
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

    if args.dry_run:
        backend_url, frontend_url = build_urls(args.slug, args.domain)
        print("--- DRY RUN : rien ne sera créé ---")
        print(f"Postgres      : smartticket-{args.slug}-postgres (plan={args.postgres_plan}, version={args.postgres_version})")
        print(f"Backend       : {backend_service_name(args.slug)} (plan={args.web_plan}) — repo={args.repo}@{args.branch}, rootDir=backend")
        print(f"              URL prédite : {backend_url}")
        print(f"Frontend      : {frontend_service_name(args.slug)} (plan={args.web_plan}) — repo={args.repo}@{args.branch}, rootDir=frontend")
        print(f"              URL prédite : {frontend_url}")
        print(f"              NEXT_PUBLIC_API_URL sera posée à : {backend_url}")
        print(f"Admin email   : {args.admin_email}")
        if not args.domain:
            print("Domaine       : aucun — URLs *.onrender.com ci-dessus (déterministes, cf. build_urls())")
        print("Secrets générés (non affichés en dry-run — regénérés à chaque exécution réelle)")
        return 0

    result = provision(
        client_name=args.name, slug=args.slug, postgres_plan=args.postgres_plan,
        admin_email=args.admin_email, domain=args.domain, web_plan=args.web_plan,
        postgres_version=args.postgres_version, repo=args.repo, branch=args.branch,
    )

    if result.status != "active":
        print(f"\nÉchec du provisioning : {result.error}", file=sys.stderr)
        return 1

    print("\n--- Instance provisionnée ---")
    print(f"Client        : {args.name} ({result.slug})")
    print(f"Frontend      : {result.frontend_url}")
    print(f"Backend       : {result.backend_url}")
    print(f"VENDOR_KEY    : {result.vendor_key}  (à conserver en lieu sûr — coupe-circuit d'abonnement)")
    print(f"Lien de setup : {result.setup_url}")
    print("                (à usage unique, expire après un délai fixé côté instance —")
    print("                 défaut 48h, ADMIN_SETUP_TOKEN_EXPIRE_HOURS)")
    if result.welcome_email_sent:
        print(f"Email         : envoyé à {args.admin_email} (via Brevo)")
    else:
        print(f"Email         : NON envoyé (voir logs ci-dessus) — transmets le lien de setup à {args.admin_email} manuellement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
