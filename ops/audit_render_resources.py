#!/usr/bin/env python3
"""Audit LECTURE SEULE des ressources Render dont le nom commence par un préfixe donné.

Ne crée, ne modifie, ne supprime AUCUNE ressource — n'appelle que GET /services et
GET /postgres (cf. render_client.list_services / list_postgres_instances). Sert à retrouver
les ressources qui pourraient facturer sans trace dans ops/instances.db : soit parce que le
registre local n'a pas suivi un changement de machine (il est gitignoré, cf. ops/README.md),
soit parce qu'une suppression a échoué avant le correctif de delete_client.py du 2026-07-16
(qui pouvait retirer la ligne du registre même quand les suppressions Render échouaient).

Usage :
    python audit_render_resources.py
    python audit_render_resources.py --prefix smartticket-acme-

PowerShell, si RENDER_API_KEY n'est pas déjà dans l'environnement :
    $env:RENDER_API_KEY = "rnd_xxx"   # Render -> Account Settings -> API Keys
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
    parser.add_argument("--prefix", default="smartticket-test-", help="Préfixe de nom Render à rechercher (défaut : smartticket-test-)")
    args = parser.parse_args()

    try:
        render.ensure_configured()
    except render.RenderAPIError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        print(
            "\nRENDER_API_KEY doit être exportée AVANT de lancer cet audit. PowerShell :\n"
            '  $env:RENDER_API_KEY = "rnd_xxx"   # Render -> Account Settings -> API Keys\n',
            file=sys.stderr,
        )
        return 1

    db.init_db()
    known_ids = set()
    for row in db.list_instances():
        known_ids.update(
            rid for rid in (row["render_backend_service_id"], row["render_frontend_service_id"], row["render_database_id"])
            if rid
        )

    print(f"Recherche des ressources Render dont le nom commence par '{args.prefix}'...\n")
    services = render.list_services(name_prefix=args.prefix)
    postgres_instances = render.list_postgres_instances(name_prefix=args.prefix)

    if not services and not postgres_instances:
        print("Aucune ressource trouvée.")
        return 0

    rows = []
    for s in services:
        rows.append({
            "nom": s["name"], "id": s["id"], "type": s["type"],
            "statut": "suspendu" if s.get("suspended") == "suspended" else "actif",
            "cree_le": s["createdAt"], "dashboard": s["dashboardUrl"],
            "connu": s["id"] in known_ids,
        })
    for p in postgres_instances:
        rows.append({
            "nom": p["name"], "id": p["id"], "type": "postgres",
            "statut": p["status"],
            "cree_le": p["createdAt"], "dashboard": p["dashboardUrl"],
            "connu": p["id"] in known_ids,
        })
    rows.sort(key=lambda r: r["cree_le"])

    for r in rows:
        trace = "présente dans instances.db" if r["connu"] else "ABSENTE d'instances.db — orpheline probable"
        print(f"- {r['nom']}  (type={r['type']}, id={r['id']})")
        print(f"    statut    : {r['statut']}")
        print(f"    créée le  : {r['cree_le']}")
        print(f"    dashboard : {r['dashboard']}")
        print(f"    registre  : {trace}")
        print()

    orphans = [r for r in rows if not r["connu"]]
    print(f"Total : {len(rows)} ressource(s), dont {len(orphans)} sans trace dans instances.db.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
