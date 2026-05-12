import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import INGEST_JOBS, get_current_user, get_user_by_email, is_admin_or_sav

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Base de connaissances"])


@router.post("/knowledge-base/ingest-url", response_model=schemas.KnowledgeIngestResponse, summary="Indexer une URL ou un sitemap dans la base de connaissances")
def ingest_knowledge_base(payload: schemas.KnowledgeIngestRequest, background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not is_admin_or_sav(requester):
        raise HTTPException(status_code=403, detail="Accès refusé")
    try:
        from ingest_postgres import ingest_to_postgres
        job_id = str(uuid.uuid4())
        INGEST_JOBS[job_id] = {"status": "running", "started_at": datetime.utcnow().isoformat(),
                               "url": str(payload.url), "category": payload.category or "", "result": None, "error": None}

        def _run(job_id_value: str, url_value: str, category_value: str | None):
            job_state = INGEST_JOBS[job_id_value]
            try:
                result = ingest_to_postgres(url=url_value, category=category_value, job_state=job_state)
                INGEST_JOBS[job_id_value].update({"status": "completed", "result": result})
            except Exception as e:
                INGEST_JOBS[job_id_value].update({"status": "failed", "error": str(e)})
            finally:
                INGEST_JOBS[job_id_value]["finished_at"] = datetime.utcnow().isoformat()

        background_tasks.add_task(_run, job_id, str(payload.url), payload.category)
        return {"status": "started", "message": "Indexation lancée en arrière-plan.", "url": str(payload.url), "category": payload.category or "", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur ingestion: {str(e)}")


@router.get("/knowledge-base/ingest-status", summary="Vérifier le statut d'un job d'indexation")
def ingest_status(job_id: str, current_user: str = Depends(get_current_user)):
    if job_id not in INGEST_JOBS:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return INGEST_JOBS[job_id]


@router.get("/knowledge-base/robots-check", summary="Analyser le robots.txt et le sitemap d'un domaine")
def robots_check(url: str, current_user: str = Depends(get_current_user)):
    from ingest_postgres import analyze_robots_and_sitemap
    try:
        return analyze_robots_and_sitemap(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {str(e)}")


@router.get("/knowledge-base/sources", summary="Lister les sources indexées")
def get_knowledge_sources(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import func as sqlfunc
    rows = (db.query(models.KnowledgeBase.source, models.KnowledgeBase.category,
                     sqlfunc.count(models.KnowledgeBase.id).label("chunks"),
                     sqlfunc.min(models.KnowledgeBase.date_creation).label("date_creation"))
            .filter(models.KnowledgeBase.source.isnot(None))
            .group_by(models.KnowledgeBase.source, models.KnowledgeBase.category)
            .order_by(sqlfunc.min(models.KnowledgeBase.date_creation).desc()).all())
    return [{"source": r.source, "category": r.category, "chunks": r.chunks,
             "date_creation": r.date_creation.isoformat() if r.date_creation else None} for r in rows]


@router.delete("/knowledge-base/sources", summary="Supprimer une source de la base de connaissances")
def delete_knowledge_source(source: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not is_admin_or_sav(requester):
        raise HTTPException(status_code=403, detail="Accès refusé")
    deleted = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.source == source).delete()
    db.commit()
    logger.info("[delete-source] user=%s deleted source='%s' (%d rows)", current_user, source, deleted)
    return {"deleted": deleted, "source": source}


@router.post("/knowledge-base/ingest-file", response_model=schemas.KnowledgeIngestResponse, summary="Indexer un fichier PDF, DOCX ou TXT")
async def ingest_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), category: str = Form(None), current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    requester = get_user_by_email(db, current_user)
    if not requester or not is_admin_or_sav(requester):
        raise HTTPException(status_code=403, detail="Accès refusé")
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("txt", "docx", "pdf"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers .pdf, .txt et .docx sont acceptés.")
    file_bytes = await file.read()
    from ingest_postgres import ingest_file_to_postgres
    job_id = str(uuid.uuid4())
    INGEST_JOBS[job_id] = {"status": "running", "started_at": datetime.utcnow().isoformat(),
                           "filename": filename, "category": category or "", "result": None, "error": None}

    def _run(job_id_value: str, bytes_value: bytes, name: str, cat: str | None):
        try:
            result = ingest_file_to_postgres(bytes_value, name, cat)
            INGEST_JOBS[job_id_value].update({"status": "completed", "result": result})
        except Exception as e:
            INGEST_JOBS[job_id_value].update({"status": "failed", "error": str(e)})
        finally:
            INGEST_JOBS[job_id_value]["finished_at"] = datetime.utcnow().isoformat()

    background_tasks.add_task(_run, job_id, file_bytes, filename, category)
    return {"status": "started", "message": f"Indexation de '{filename}' lancée en arrière-plan.", "job_id": job_id}
