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

ATTENTION : non testé contre un vrai compte Render, cf. render_client.py.
"""
import argparse
import logging
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import db
import render_client as render

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


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

    resources = [
        ("service backend", "service", instance["render_backend_service_id"]),
        ("service frontend", "service", instance["render_frontend_service_id"]),
        ("base Postgres", "postgres", instance["render_database_id"]),
    ]
    print("Suppression des ressources Render (backend, frontend, Postgres)...")
    # render.delete_resources() : même boucle best-effort qu'avant (continue même si une
    # suppression échoue), désormais partagée avec le rollback de provision_client.py plutôt
    # que réimplémentée ici.
    failed = render.delete_resources(resources)

    if failed:
        # Ne JAMAIS retirer/modifier la ligne tant qu'une ressource Render survit : c'est le
        # seul registre qui permette de la retrouver pour un nettoyage manuel. Même logique
        # que _rollback() dans provision_client.py sur un rollback incomplet (statut='failed'
        # + IDs orphelins dans notes, ligne conservée) — bug réel du 2026-07-16 corrigé ici :
        # une RENDER_API_KEY manquante faisait échouer les 3 suppressions, mais la ligne
        # était quand même retirée juste après, rendant les 3 ressources facturées introuvables.
        details = "; ".join(f"{label} (id={resource_id})" for label, _, resource_id in failed)
        db.update_instance(args.slug, statut="deletion_failed", notes=details)
        print(
            f"\nÉCHEC PARTIEL : {details} — vérifier manuellement sur le dashboard Render "
            "(ressources potentiellement encore facturées). La ligne reste dans "
            f"instances.db (statut 'deletion_failed', IDs dans notes) : NE PAS relancer "
            "aveuglément, nettoyer sur Render puis relancer ce script (il retentera "
            "uniquement les ressources encore référencées) ou supprimer la ligne à la main "
            "une fois le nettoyage confirmé.",
            file=sys.stderr,
        )
        return 1

    if args.keep_row:
        db.update_instance_status(args.slug, "supprimee")
        print("Ligne conservée dans instances.db avec statut 'supprimee'.")
    else:
        db.delete_instance_row(args.slug)
        print("Ligne retirée de instances.db.")

    print(f"\nInstance '{args.slug}' décommissionnée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
