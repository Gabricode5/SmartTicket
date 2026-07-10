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
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import db
import render_client as render


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

    if not args.yes:
        answer = input(f"\nSupprimer DÉFINITIVEMENT l'instance '{args.slug}' et toutes ses données ? Tape le slug pour confirmer : ")
        if answer.strip() != args.slug:
            print("Confirmation invalide — annulation.")
            return 1

    errors = []
    for label, deleter in [
        ("service backend", lambda: render.delete_service(instance["render_backend_service_id"])),
        ("service frontend", lambda: render.delete_service(instance["render_frontend_service_id"])),
        ("base Postgres", lambda: render.delete_postgres(instance["render_database_id"])),
    ]:
        try:
            print(f"Suppression du {label}...")
            deleter()
        except render.RenderAPIError as exc:
            print(f"  Échec ({label}) : {exc}", file=sys.stderr)
            errors.append(label)

    if args.keep_row:
        db.update_instance_status(args.slug, "supprimee")
        print("Ligne conservée dans instances.db avec statut 'supprimee'.")
    else:
        db.delete_instance_row(args.slug)
        print("Ligne retirée de instances.db.")

    if errors:
        print(f"\nAttention : échec sur {', '.join(errors)} — vérifier manuellement sur le dashboard Render (ressources potentiellement encore facturées).", file=sys.stderr)
        return 1

    print(f"\nInstance '{args.slug}' décommissionnée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
