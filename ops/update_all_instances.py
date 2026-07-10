#!/usr/bin/env python3
"""Propage un correctif/une nouvelle version à toute la flotte d'instances actives, en
déclenchant un redeploy Render sur chaque backend/frontend — cohérent avec la décision
mono-repo/mono-branche (docs/FLEET_PROVISIONING_PLAN.md) : toutes les instances déploient
la même branche `main`, donc pas de merge/rebase par client, juste un redeploy.

Usage :
    python update_all_instances.py --dry-run
    python update_all_instances.py --only acme-corp,contoso     # rollout progressif
    python update_all_instances.py                              # toute la flotte active

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
    parser.add_argument("--dry-run", action="store_true", help="Liste ce qui serait redéployé sans le faire")
    parser.add_argument("--only", default=None, help="Slugs séparés par des virgules (rollout progressif), ex: acme-corp,contoso")
    args = parser.parse_args()

    instances = db.list_instances(statut="active")
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        instances = [i for i in instances if i["slug"] in wanted]
        missing = wanted - {i["slug"] for i in instances}
        if missing:
            print(f"Attention : slugs introuvables ou non actifs, ignorés : {', '.join(sorted(missing))}", file=sys.stderr)

    if not instances:
        print("Aucune instance active à mettre à jour.")
        return 0

    print(f"{len(instances)} instance(s) ciblée(s) : {', '.join(i['slug'] for i in instances)}")

    if args.dry_run:
        print("--- DRY RUN : aucun redeploy déclenché ---")
        for instance in instances:
            print(f"  {instance['slug']} : backend={instance['render_backend_service_id']}, frontend={instance['render_frontend_service_id']}")
        return 0

    failures = []
    for instance in instances:
        slug = instance["slug"]
        print(f"Redeploy de '{slug}'...")
        try:
            render.trigger_deploy(instance["render_backend_service_id"])
            render.trigger_deploy(instance["render_frontend_service_id"])
        except render.RenderAPIError as exc:
            print(f"  Échec pour '{slug}' : {exc}", file=sys.stderr)
            failures.append(slug)

    if failures:
        print(f"\n{len(failures)} instance(s) en échec : {', '.join(failures)}", file=sys.stderr)
        return 1

    print("\nTous les redeploys ont été déclenchés. Ils s'exécutent en arrière-plan côté Render — vérifier leur statut sur le dashboard ou via render_client.get_latest_deploy().")
    return 0


if __name__ == "__main__":
    sys.exit(main())
