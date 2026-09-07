"""Worker : ouvre une session GLPI, boucle run_once toutes POLL_INTERVAL_SECONDS.

Entrée : `python -m glpi_connector.worker`.
"""
import logging
import time

from glpi_connector import config
from glpi_connector.db import SessionLocal
from glpi_connector.glpi_client import GlpiClient
from glpi_connector.poller import run_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("glpi_connector.worker")


def run_forever(*, _max_iterations: int | None = None, _sleep=time.sleep) -> None:
    """_max_iterations / _sleep : points d'injection pour les tests, pas pour la prod."""
    logger.info(
        "Démarrage worker GLPI — DRY_RUN=%s, intervalle=%ss, statuts=%s, suivi=%s(privé=%s)",
        config.DRY_RUN, config.POLL_INTERVAL_SECONDS, config.GLPI_TICKET_STATUS_FILTER,
        config.GLPI_FOLLOWUP_ITEMTYPE, config.FOLLOWUP_IS_PRIVATE,
    )
    client = GlpiClient()
    client.init_session()
    iterations = 0
    try:
        while _max_iterations is None or iterations < _max_iterations:
            with SessionLocal() as db:
                try:
                    run_once(db, client)
                except Exception:  # noqa: BLE001
                    logger.exception("Passage du poller en échec — on réessaiera au prochain cycle.")
            iterations += 1
            if _max_iterations is not None and iterations >= _max_iterations:
                break
            _sleep(config.POLL_INTERVAL_SECONDS)
    finally:
        client.kill_session()


if __name__ == "__main__":  # pragma: no cover
    run_forever()
