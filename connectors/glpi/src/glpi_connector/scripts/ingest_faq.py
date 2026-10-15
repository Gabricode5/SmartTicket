"""Ingestion en masse des FAQ .txt d'un dossier dans rag_core (one-shot, manuel).

Usage :
    python -m glpi_connector.scripts.ingest_faq /app/faq --category faq
"""
import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("glpi_connector.scripts.ingest_faq")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Dossier contenant les .txt à ingérer")
    parser.add_argument(
        "--category", default=None,
        help="Catégorie rag_core (défaut : RAG_INGEST_DEFAULT_CATEGORY)",
    )
    args = parser.parse_args()

    from rag_core.db import SessionLocal
    from rag_core.ingest import IngestError, ingest_file

    files = sorted(args.directory.glob("*.txt"))
    if not files:
        logger.error("Aucun fichier .txt trouvé dans %s", args.directory)
        return 1

    total_inserted = 0
    failures = 0
    with SessionLocal() as db:
        for path in files:
            try:
                result = ingest_file(db, path.read_bytes(), path.name, category=args.category)
                logger.info(
                    "%s : %d chunks insérés, %d rejetés%s",
                    path.name, result.inserted, result.chunks_rejected,
                    " (tronqué)" if result.truncated else "",
                )
                total_inserted += result.inserted
            except IngestError as exc:
                logger.error("%s : échec ingestion -- %s", path.name, exc)
                failures += 1

    logger.info(
        "Terminé : %d fichiers traités, %d chunks insérés au total, %d échecs.",
        len(files), total_inserted, failures,
    )
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
