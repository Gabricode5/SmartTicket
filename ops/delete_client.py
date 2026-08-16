#!/usr/bin/env python3
"""Décommissionne une instance cliente (offboarding) — symétrique de provision_client.py,
cf. docs/FLEET_PROVISIONING_PLAN.md : supprime les services Render (backend, frontend,
Postgres) et retire l'instance de ops/instances.db.

Action destructrice et irréversible côté Render (suppression définitive de la base du
client, y compris ses backups). Confirmation explicite requise.

Usage :
    python delete_client.py --slug acme-corp --dry-run
    python delete_client.py --slug acme-corp                 # demande confirmation interactive
    python delete_client.py --slug acme-corp --yes            # sans confirmation (scripts)

La logique métier vit dans delete_instance() — une fonction pure (pas d'input(), pas de
print(), uniquement une valeur de retour), même pattern que provision() dans
provision_client.py, appelable telle quelle par un autre appelant (ex: ops/fleet_admin.py,
Partie B.2bis) sans dupliquer la logique de suppression. main() n'est qu'un mince wrapper
CLI : parse les arguments, gère --dry-run et la confirmation interactive, affiche le
résultat pour un humain.
"""
import argparse
import dataclasses
import logging
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import db
import render_client as render

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DeleteResult:
    slug: str
    status: str  # "deleted" | "failed" | "not_found"
    error: str | None = None


def delete_instance(slug: str, *, keep_row: bool = False) -> DeleteResult:
    """Supprime les ressources Render d'une instance et met à jour instances.db en
    conséquence. RENDER_API_KEY est validée avant toute action (render.ensure_configured()) ;
    ne lève jamais — retourne un DeleteResult typé, y compris sur échec, pour que l'appelant
    (CLI ou une future UI) affiche le résultat RÉEL sans avoir à parser une exception."""
    instance = db.get_instance(slug)
    if not instance:
        return DeleteResult(slug=slug, status="not_found", error=f"Aucune instance avec le slug '{slug}' dans ops/instances.db.")

    try:
        render.ensure_configured()
    except render.RenderAPIError as exc:
        return DeleteResult(slug=slug, status="failed", error=str(exc))

    resources = [
        ("service backend", "service", instance["render_backend_service_id"]),
        ("service frontend", "service", instance["render_frontend_service_id"]),
        ("base Postgres", "postgres", instance["render_database_id"]),
    ]
    # render.delete_resources() : boucle best-effort (continue même si une suppression
    # échoue), partagée avec le rollback de provision_client.py plutôt que réimplémentée ici.
    failed = render.delete_resources(resources)

    if failed:
        # Ne JAMAIS retirer/modifier la ligne tant qu'une ressource Render survit : c'est le
        # seul registre qui permette de la retrouver pour un nettoyage manuel. Même logique
        # que _rollback() dans provision_client.py sur un rollback incomplet (statut='failed'
        # + IDs orphelins dans notes, ligne conservée) — bug réel du 2026-07-16 corrigé ici :
        # une RENDER_API_KEY manquante faisait échouer les 3 suppressions, mais la ligne
        # était quand même retirée juste après, rendant les 3 ressources facturées introuvables.
        details = "; ".join(f"{label} (id={resource_id})" for label, _, resource_id in failed)
        db.update_instance(slug, statut="deletion_failed", notes=details)
        return DeleteResult(slug=slug, status="failed", error=(
            f"{len(failed)} ressource(s) Render n'ont pas pu être supprimées : {details}. "
            "Vérifier manuellement sur le dashboard Render (ressources potentiellement "
            "encore facturées) — ligne conservée (statut 'deletion_failed') pour ne pas "
            "perdre la trace des IDs orphelins."
        ))

    if keep_row:
        db.update_instance_status(slug, "supprimee")
    else:
        db.delete_instance_row(slug)

    return DeleteResult(slug=slug, status="deleted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", required=True, help="Slug de l'instance à supprimer")
    parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait supprimé sans le faire")
    parser.add_argument("--yes", action="store_true", help="Ignore la confirmation interactive (usage scripté)")
    parser.add_argument("--keep-row", action="store_true", help="Conserve la ligne dans instances.db (statut 'supprimee') au lieu de la retirer complètement — utile pour garder une trace historique")
    args = parser.parse_args()

    instance = db.get_instance(args.slug)
    if not instance:
        print(f"Erreur : aucune instance avec le slug '{args.slug}' dans ops/instances.db.", file=sys.stderr)
        return 1

    print(f"Instance ciblée : {instance['client_name']} ({args.slug})")
    print(f"  Backend Postgres : {instance['render_database_id']}")
    print(f"  Backend service  : {instance['render_backend_service_id']}")
    print(f"  Frontend service : {instance['render_frontend_service_id']}")

    if args.dry_run:
        print("--- DRY RUN : rien ne sera supprimé ---")
        return 0

    # Vérifiée ici AUSSI (en plus de delete_instance()) pour ne pas faire taper la
    # confirmation ci-dessous à un humain avant de lui apprendre que la clé manque.
    try:
        render.ensure_configured()
    except render.RenderAPIError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    if not args.yes:
        answer = input(f"\nSupprimer DÉFINITIVEMENT l'instance '{args.slug}' et toutes ses données ? Tape le slug pour confirmer : ")
        if answer.strip() != args.slug:
            print("Confirmation invalide — annulation.")
            return 1

    print("Suppression des ressources Render (backend, frontend, Postgres)...")
    result = delete_instance(args.slug, keep_row=args.keep_row)

    if result.status == "not_found":
        print(f"Erreur : {result.error}", file=sys.stderr)
        return 1

    if result.status == "failed":
        print(f"\nÉCHEC PARTIEL : {result.error}", file=sys.stderr)
        return 1

    if args.keep_row:
        print("Ligne conservée dans instances.db avec statut 'supprimee'.")
    else:
        print("Ligne retirée de instances.db.")

    print(f"\nInstance '{args.slug}' décommissionnée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
