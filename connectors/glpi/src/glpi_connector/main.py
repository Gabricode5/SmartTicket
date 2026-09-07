"""API du connecteur (health check Render + admin).

  GET  /health        -> état + dry_run (exempté de tout, pour le health check)
  GET  /admin/status  -> compteurs processed_tickets
  POST /admin/poll     -> déclenche UN passage run_once (respecte DRY_RUN)
"""
import logging

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from glpi_connector import config, store
from glpi_connector.db import get_session
from glpi_connector.glpi_client import GlpiClient
from glpi_connector.poller import run_once

logger = logging.getLogger(__name__)

app = FastAPI(title="Connecteur GLPI ↔ rag_core", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "dry_run": config.DRY_RUN,
        "response_mode": config.RESPONSE_MODE,
        "followup_itemtype": config.GLPI_FOLLOWUP_ITEMTYPE,
        "followup_is_private": config.FOLLOWUP_IS_PRIVATE,
    }


@app.get("/admin/status")
def admin_status(db: Session = Depends(get_session)) -> dict:
    return {"dry_run": config.DRY_RUN, "processed": store.counts_by_status(db)}


@app.post("/admin/poll")
def admin_poll(db: Session = Depends(get_session)) -> dict:
    client = GlpiClient()
    with client:
        stats = run_once(db, client)
    return {
        "dry_run": config.DRY_RUN,
        "seen": stats.seen,
        "already_processed": stats.already_processed,
        "answered": stats.answered,
        "dry_run_previews": len(stats.would_post),
        "skipped_empty": stats.skipped_empty,
        "errors": stats.errors,
    }
