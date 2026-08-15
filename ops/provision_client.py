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
    - Si BREVO_API_KEY est exportée : SMTP_FROM DOIT l'être aussi, avec une adresse validée
      dans Brevo → Senders (sans quoi Brevo répond 401 sur CHAQUE envoi — l'email de
      bienvenue ops/notify.py ET, plus grave, les emails de vérification/reset de TOUTES les
      instances provisionnées, cf. bug réel du 2026-07-16 : seule gabriel.guery10@gmail.com
      était validée, "no-reply@smartticket.app" ne l'était pas et échouait silencieusement,
      l'erreur étant interceptée et seulement loggée côté backend/email_utils.py). En
      production, valider une adresse sur le domaine (ex: noreply@smartticket.fr, avec
      SPF/DKIM) plutôt qu'une adresse Gmail.
    - Si --domain est fourni : le domaine doit déjà exister et pointer vers Render (wildcard
      DNS), cf. Phase 0. Sans --domain, l'instance reste accessible via son URL *.onrender.com.

ATTENTION : plusieurs essais réels contre un vrai compte Render effectués depuis le
2026-07-14 (cf. render_client.py pour le détail des écarts trouvés et corrigés avec le
schéma OpenAPI réel de Render). Confirmés fonctionner en pratique : création de la base
Postgres, rollback sur échec partiel, POST /v1/setup (amorçage du compte admin par token).

BUG DE FOND trouvé le 2026-08-15, en conditions réelles (instance martin-technologies) :
l'URL *.onrender.com d'un service n'est PAS déterministe à partir du nom qu'on lui donne,
contrairement à ce que la doc publique Render laissait penser et à ce que ce module a
longtemps supposé (cf. l'ancienne build_urls(), qui prédisait "https://{nom}.onrender.com").
Preuve : un service nommé "smartticket-martin-technologies-9abaae-backend" a été assigné à
l'URL réelle "...-9abaae-xml6.onrender.com" par Render (suffixe supplémentaire imprévisible)
— la prédiction pointait vers une URL qui ne répondait jamais (404), rendant NEXT_PUBLIC_API_URL,
CORS_ORIGINS, FRONTEND_URL et le lien de setup tous faux malgré un provisioning "réussi" côté
Render (backend Online, frontend Live). provision() ne prédit donc plus JAMAIS l'URL d'un
service *.onrender.com : elle est relue depuis l'API (GET /services/{id}, champ
serviceDetails.url) juste après le premier déploiement de CHAQUE service. Conséquence sur
l'ordre : le backend a besoin de CORS_ORIGINS/FRONTEND_URL (= URL réelle du frontend), mais
le frontend n'existe pas encore quand le backend est créé — le backend est donc redéployé une
seconde fois, une fois l'URL réelle du frontend connue (render.set_env_vars + trigger_deploy).
Avec --domain, ce problème ne se pose pas : le domaine personnalisé est choisi PAR NOUS
(build_domain_urls()), Render ne peut pas le renommer — ce chemin reste inchangé, mais
demeure non testé en conditions réelles (en particulier l'attente du certificat TLS).

Bug corrigé le 2026-07-14 (frontend) et 2026-07-17 (backend), toujours valables : Next.js
bake les rewrites de next.config.ts au BUILD, jamais au runtime (NEXT_PUBLIC_API_URL doit
donc être correcte AVANT le premier build du frontend, jamais corrigée après coup sans
nouveau build) — cf. frontend/scripts/verify-production-build.mjs, lancé en CI juste après
`next build`. backend/email_utils.py construit les liens de vérification d'email/reset
password à partir de FRONTEND_URL (défaut "http://localhost:3005" si absente) — email bien
reçu (Brevo fonctionnait) mais lien cassé en ERR_CONNECTION_REFUSED tant qu'elle n'est pas
injectée. FRONTEND_URL fait partie de backend_env, même valeur que CORS_ORIGINS.

Toujours lancer avec --dry-run d'abord, puis sur une instance de test jetable avant tout
client réel (Phase 4 du plan).

La logique métier vit dans provision() — une fonction pure (pas d'input(), pas de print()
comme moyen de retour, uniquement du logging + une valeur de retour) appelable telle quelle
par un futur déclencheur automatisé (ex: webhook de paiement). main() n'est qu'un mince
wrapper CLI : parse les arguments, gère le --dry-run (qui n'appelle jamais provision(), pour
ne jamais faire de vrai appel réseau), affiche le résultat pour un humain.
"""
import argparse
import logging
import os
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


def generate_render_suffix() -> str:
    """6 caractères hex (secrets.token_hex(3), ~16M combinaisons) ajoutés au nom de CHAQUE
    ressource Render créée par un provisioning donné — cf. backend_service_name() ci-dessous
    pour le pourquoi (réutilisation immédiate d'un slug)."""
    return secrets.token_hex(3)


def backend_service_name(slug: str, render_suffix: str) -> str:
    return f"smartticket-{slug}-{render_suffix}-backend"


def frontend_service_name(slug: str, render_suffix: str) -> str:
    return f"smartticket-{slug}-{render_suffix}-frontend"


def postgres_name(slug: str, render_suffix: str) -> str:
    return f"smartticket-{slug}-{render_suffix}-postgres"


def build_domain_urls(slug: str, domain: str) -> tuple[str, str]:
    """Retourne (backend_url, frontend_url) pour un domaine personnalisé — déterministe
    car NOUS choisissons ce domaine (posé plus tard via add_custom_domain), Render ne peut
    pas le renommer. Distinct des URLs *.onrender.com : cf. le bug réel du 2026-08-15
    documenté sur provision(), qui ne prédit plus JAMAIS ces dernières."""
    return f"https://{slug}-api.{domain}", f"https://{slug}.{domain}"


def _shared_secret(env_var: str, required: bool = True) -> str:
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

    render_suffix = generate_render_suffix()
    backend_name = backend_service_name(slug, render_suffix)
    frontend_name = frontend_service_name(slug, render_suffix)
    db_name = postgres_name(slug, render_suffix)

    secret_key = generate_secret()
    vendor_key = generate_secret()
    admin_setup_token = generate_secret()  # jamais un mot de passe : cf. POST /v1/setup côté backend

    brevo_api_key = _shared_secret("BREVO_API_KEY", required=False)
    smtp_from = os.getenv("SMTP_FROM", "")
    if brevo_api_key and not smtp_from:
        # Échec Brevo 401 réel du 2026-07-16 : le sender par défaut de backend/email_utils.py
        # ("no-reply@smartticket.app") n'est validé nulle part dans Brevo → Senders. Toutes
        # les instances provisionnées sans SMTP_FROM explicite auraient donc leurs emails de
        # vérification/reset qui échouent en 401, SILENCIEUSEMENT (l'exception est
        # interceptée et seulement loggée côté backend, jamais remontée à l'utilisateur) —
        # mieux vaut échouer fort ici, avant de créer quoi que ce soit sur Render.
        raise RuntimeError(
            "BREVO_API_KEY est définie mais SMTP_FROM ne l'est pas : chaque instance "
            "provisionnée utiliserait l'adresse expéditrice par défaut de "
            "backend/email_utils.py, qui n'est validée dans aucun compte Brevo → Senders. "
            "Tous les emails (vérification, reset) échoueraient en 401 sans que personne ne "
            "s'en aperçoive. Exportez SMTP_FROM avec une adresse validée dans Brevo avant de "
            "relancer le provisioning."
        )

    # Avec --domain : déterministe, nous choisissons le domaine (cf. build_domain_urls()).
    # Sans --domain : (None, None), l'URL réelle *.onrender.com de chaque service n'est
    # connue qu'après sa création — jamais prédite, cf. docstring du module (bug du
    # 2026-08-15).
    domain_backend_url, domain_frontend_url = build_domain_urls(slug, domain) if domain else (None, None)

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

        # Sans --domain, CORS_ORIGINS/FRONTEND_URL ne peuvent pas encore être correctes : le
        # frontend n'existe pas encore, donc son URL réelle est inconnue (cf. docstring du
        # module). Posées vides pour l'instant — corrigées et redéployées plus bas, une fois
        # l'URL réelle du frontend connue. Avec --domain, la valeur finale est déjà connue.
        backend_env = {
            "DATABASE_URL": database_url,
            "SECRET_KEY": secret_key,
            "ALGORITHM": "HS256",
            "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
            "CORS_ORIGINS": domain_frontend_url or "",
            # Sans ça, backend/email_utils.py retombait sur son défaut
            # ("http://localhost:3005") pour CONSTRUIRE LES LIENS de tous les emails
            # transactionnels (vérification d'email, reset password, invitation en masse) —
            # bug réel du 2026-07-17 : email reçu (Brevo fonctionnait), mais le lien pointait
            # sur localhost -> ERR_CONNECTION_REFUSED côté client. Le lien de setup
            # (ops/notify.py) n'est PAS affecté : setup_url est construit plus bas à partir de
            # frontend_url, jamais via cette variable backend.
            "FRONTEND_URL": domain_frontend_url or "",
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
            "BREVO_API_KEY": brevo_api_key,
            # Sans ça, backend/email_utils.py retombait sur son défaut
            # ("no-reply@smartticket.app"), jamais validé dans Brevo → Senders : les emails de
            # vérification/reset de CHAQUE instance provisionnée échouaient en 401 sans que
            # personne ne s'en aperçoive (bug réel du 2026-07-16). Garanti non vide à ce point
            # si brevo_api_key est non vide (cf. le fail-fast plus haut) ; sinon transmis quand
            # même tel quel (vide ou une valeur explicite) pour rester cohérent avec le défaut
            # SMTP_FROM du backend si un jour SMTP_HOST est aussi câblé ici.
            "SMTP_FROM": smtp_from,
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

        # URL RÉELLE, jamais devinée — bug réel du 2026-08-15 (cf. docstring du module) :
        # l'URL *.onrender.com effectivement assignée par Render peut différer du nom de
        # service demandé (suffixe supplémentaire imprévisible constaté en conditions
        # réelles). Relue depuis l'API après le premier déploiement, pas depuis une
        # convention de nommage.
        if domain_backend_url:
            backend_url = domain_backend_url
        else:
            backend_service = render.get_service(backend_service_id)
            backend_url = backend_service.get("serviceDetails", {}).get("url", "")
            if not backend_url:
                raise RuntimeError(f"Impossible de récupérer l'URL réelle du service backend {backend_service_id} (serviceDetails.url absent de la réponse API).")
        db.update_instance(slug, backend_url=backend_url)

        frontend_env = {
            "NEXT_PUBLIC_API_URL": backend_url,
            # White-label du nom de marque (Phase 0 bis, 2026-08-15) — même piège que
            # NEXT_PUBLIC_API_URL : NEXT_PUBLIC_* est bakée au BUILD Next.js, jamais
            # réévaluée au runtime, donc posée ici AVANT la création du service (premier
            # build). Valeur = client_name (déjà capturé plus haut), pas slug : c'est le nom
            # affiché aux utilisateurs finaux du client, pas l'identifiant technique.
            "NEXT_PUBLIC_BRAND_NAME": client_name,
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

        if domain:
            logger.info("Attachement du domaine personnalisé %s...", domain_frontend_url)
            render.add_custom_domain(frontend_service_id, f"{slug}.{domain}")
            frontend_url = domain_frontend_url
        else:
            # Même lecture RÉELLE que pour le backend ci-dessus, jamais devinée.
            frontend_service = render.get_service(frontend_service_id)
            frontend_url = frontend_service.get("serviceDetails", {}).get("url", "")
            if not frontend_url:
                raise RuntimeError(f"Impossible de récupérer l'URL réelle du service frontend {frontend_service_id} (serviceDetails.url absent de la réponse API).")

            # Le backend a été créé avec CORS_ORIGINS/FRONTEND_URL vides (frontend_url était
            # encore inconnue à ce moment) — maintenant qu'elle l'est, on corrige et on
            # redéploie. Avec --domain, inutile : ces valeurs étaient déjà correctes dès la
            # création du backend (build_domain_urls() est déterministe).
            logger.info("Mise à jour de CORS_ORIGINS/FRONTEND_URL du backend avec l'URL réelle du frontend, et redéploiement...")
            backend_env["CORS_ORIGINS"] = frontend_url
            backend_env["FRONTEND_URL"] = frontend_url
            render.set_env_vars(backend_service_id, backend_env)
            render.trigger_deploy(backend_service_id)
            if not render.wait_for_deploy_live(backend_service_id):
                logger.warning("Le redéploiement du backend (CORS_ORIGINS/FRONTEND_URL corrigées) n'est pas encore 'live' après le délai d'attente — vérifie manuellement sur Render.")

        db.update_instance(slug, frontend_url=frontend_url)
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
        # Complète une colonne déjà existante en base mais jamais renseignée jusqu'ici — pas
        # un changement de logique métier, juste la valeur qu'on connaît déjà (postgres_plan)
        # écrite là où elle était censée l'être. Utile pour la page de gestion (Partie B).
        plan_tarifaire=postgres_plan,
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
        render_suffix = generate_render_suffix()
        print("--- DRY RUN : rien ne sera créé ---")
        print(f"Postgres      : {postgres_name(args.slug, render_suffix)} (plan={args.postgres_plan}, version={args.postgres_version})")
        print(f"Backend       : {backend_service_name(args.slug, render_suffix)} (plan={args.web_plan}) — repo={args.repo}@{args.branch}, rootDir=backend")
        print(f"Frontend      : {frontend_service_name(args.slug, render_suffix)} (plan={args.web_plan}) — repo={args.repo}@{args.branch}, rootDir=frontend")
        if args.domain:
            domain_backend_url, domain_frontend_url = build_domain_urls(args.slug, args.domain)
            print(f"              URL backend (domaine)  : {domain_backend_url}")
            print(f"              URL frontend (domaine) : {domain_frontend_url}")
        else:
            print("Domaine       : aucun — URLs *.onrender.com réelles connues UNIQUEMENT après création")
            print("                de chaque service (jamais devinées, cf. bug réel du 2026-08-15 documenté")
            print("                en tête de ce fichier) : provision() les relit via l'API après coup.")
        print(f"Admin email   : {args.admin_email}")
        print(f"Suffixe Render: {render_suffix} (exemple — régénéré à chaque exécution réelle, cf. generate_render_suffix())")
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
