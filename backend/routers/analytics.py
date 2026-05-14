from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db
from dependencies import get_current_user, get_user_by_email, is_admin_or_sav

router = APIRouter(tags=["Analytics"])

REASON_LABELS = {"technique": "Technique", "complexe": "Complexe", "sensible": "Sensible", "autre": "Autre"}
REASON_COLORS = {"technique": "#0ea5e9", "complexe": "#f59e0b", "sensible": "#ef4444", "autre": "#8b5cf6"}

ALERT_THRESHOLDS = {
    "resolution_rate_critical": 50.0,
    "resolution_rate_warning": 70.0,
    "satisfaction_critical": 2.0,
    "satisfaction_warning": 3.0,
    "transfer_rate_warning": 0.30,
}


def _compute_alerts(ai_resolution_rate: float, satisfaction_score: float | None, transferred_count: int, total_sessions: int) -> list[dict]:
    alerts = []
    if total_sessions > 0:
        if ai_resolution_rate < ALERT_THRESHOLDS["resolution_rate_critical"]:
            alerts.append({"level": "critical", "metric": "ai_resolution_rate",
                           "message": f"Taux de résolution IA critique : {ai_resolution_rate}%",
                           "value": ai_resolution_rate, "threshold": ALERT_THRESHOLDS["resolution_rate_critical"]})
        elif ai_resolution_rate < ALERT_THRESHOLDS["resolution_rate_warning"]:
            alerts.append({"level": "warning", "metric": "ai_resolution_rate",
                           "message": f"Taux de résolution IA en baisse : {ai_resolution_rate}%",
                           "value": ai_resolution_rate, "threshold": ALERT_THRESHOLDS["resolution_rate_warning"]})

        transfer_rate = transferred_count / total_sessions
        if transfer_rate >= ALERT_THRESHOLDS["transfer_rate_warning"]:
            alerts.append({"level": "warning", "metric": "transfer_rate",
                           "message": f"Taux de transfert élevé : {round(transfer_rate * 100, 1)}% des sessions",
                           "value": round(transfer_rate * 100, 1), "threshold": round(ALERT_THRESHOLDS["transfer_rate_warning"] * 100)})

    if satisfaction_score is not None:
        if satisfaction_score < ALERT_THRESHOLDS["satisfaction_critical"]:
            alerts.append({"level": "critical", "metric": "satisfaction_score",
                           "message": f"Score de satisfaction critique : {satisfaction_score}/5",
                           "value": satisfaction_score, "threshold": ALERT_THRESHOLDS["satisfaction_critical"]})
        elif satisfaction_score < ALERT_THRESHOLDS["satisfaction_warning"]:
            alerts.append({"level": "warning", "metric": "satisfaction_score",
                           "message": f"Score de satisfaction bas : {satisfaction_score}/5",
                           "value": satisfaction_score, "threshold": ALERT_THRESHOLDS["satisfaction_warning"]})
    return alerts


@router.get("/analytics/stats", summary="Statistiques du service IA (taux de résolution, satisfaction, transferts)")
def get_analytics_stats(days: int = 30, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")

    from sqlalchemy import func as sqlfunc
    from_date = datetime.utcnow() - timedelta(days=days)

    total_sessions = db.query(sqlfunc.count(models.ChatSession.id)).filter(models.ChatSession.date_creation >= from_date, models.ChatSession.deleted_at.is_(None)).scalar() or 0
    transferred_sq = db.query(models.ChatMessage.id_session).filter(models.ChatMessage.type_envoyeur == "sav", models.ChatMessage.date_creation >= from_date).distinct().subquery()
    transferred_count = db.query(sqlfunc.count()).select_from(transferred_sq).scalar() or 0
    ai_resolution_rate = round((total_sessions - transferred_count) / total_sessions * 100, 1) if total_sessions > 0 else 0.0

    daily_rows = db.query(sqlfunc.date_trunc("day", models.ChatMessage.date_creation).label("day"),
                          models.ChatMessage.type_envoyeur, sqlfunc.count(models.ChatMessage.id).label("cnt")).filter(
        models.ChatMessage.date_creation >= from_date).group_by("day", models.ChatMessage.type_envoyeur).order_by("day").all()

    day_map: dict = {}
    for row in daily_rows:
        label = f"{row.day.day} {row.day.strftime('%b')}" if row.day else "?"
        if label not in day_map:
            day_map[label] = {"name": label, "IA": 0, "Humain": 0}
        if row.type_envoyeur == "ai":
            day_map[label]["IA"] += row.cnt
        elif row.type_envoyeur == "sav":
            day_map[label]["Humain"] += row.cnt

    total_rated = db.query(sqlfunc.count(models.ChatMessage.id)).filter(models.ChatMessage.type_envoyeur == "ai", models.ChatMessage.feedback.isnot(None), models.ChatMessage.date_creation >= from_date).scalar() or 0
    positive = db.query(sqlfunc.count(models.ChatMessage.id)).filter(models.ChatMessage.type_envoyeur == "ai", models.ChatMessage.feedback == 1, models.ChatMessage.date_creation >= from_date).scalar() or 0
    satisfaction_score = round(positive / total_rated * 5, 2) if total_rated > 0 else None

    sav_role = db.query(models.Role).filter(models.Role.nom_role == "sav").first()
    sav_agents = []
    if sav_role:
        sav_users = db.query(models.Utilisateur).filter(models.Utilisateur.id_role == sav_role.id, models.Utilisateur.deleted_at.is_(None)).all()
        per_agent = round(transferred_count / len(sav_users)) if sav_users else 0
        for u in sav_users:
            full_name = " ".join(filter(None, [u.prenom, u.nom])) or u.username
            sav_agents.append({"name": full_name, "initials": "".join(w[0].upper() for w in full_name.split()[:2]), "conversations": per_agent})

    reason_rows = db.query(models.ChatSession.transfer_reason, sqlfunc.count(models.ChatSession.id)).filter(
        models.ChatSession.transfer_reason.isnot(None), models.ChatSession.date_creation >= from_date, models.ChatSession.deleted_at.is_(None)).group_by(models.ChatSession.transfer_reason).all()
    transfer_reasons = [{"name": REASON_LABELS.get(r, r), "value": cnt, "color": REASON_COLORS.get(r, "#94a3b8")} for r, cnt in reason_rows]

    alerts = _compute_alerts(ai_resolution_rate, satisfaction_score, transferred_count, total_sessions)

    return {"total_sessions": total_sessions, "ai_resolution_rate": ai_resolution_rate, "transferred_count": transferred_count,
            "satisfaction_score": satisfaction_score, "daily_messages": list(day_map.values()),
            "sav_agents": sav_agents, "transfer_reasons": transfer_reasons, "alerts": alerts}


@router.get("/analytics/ai-metrics", summary="Métriques de monitoring du modèle IA (latence, erreurs, RAG)")
def get_ai_metrics(days: int = 30, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user)
    if not is_admin_or_sav(user):
        raise HTTPException(status_code=403, detail="Accès refusé")

    from sqlalchemy import func as sqlfunc
    from_date = datetime.utcnow() - timedelta(days=days)

    total_calls = db.query(sqlfunc.count(models.AICallLog.id)).filter(
        models.AICallLog.date_creation >= from_date,
        models.AICallLog.call_type == "stream",
    ).scalar() or 0

    failed_calls = db.query(sqlfunc.count(models.AICallLog.id)).filter(
        models.AICallLog.date_creation >= from_date,
        models.AICallLog.call_type == "stream",
        models.AICallLog.success == False,
    ).scalar() or 0
    error_rate = round(failed_calls / total_calls * 100, 1) if total_calls > 0 else 0.0

    avg_latency = db.query(sqlfunc.avg(models.AICallLog.latency_ms)).filter(
        models.AICallLog.date_creation >= from_date,
        models.AICallLog.call_type == "stream",
        models.AICallLog.success == True,
    ).scalar()
    avg_latency_ms = round(float(avg_latency)) if avg_latency else None

    avg_chunks = db.query(sqlfunc.avg(models.AICallLog.rag_chunks_found)).filter(
        models.AICallLog.date_creation >= from_date,
        models.AICallLog.call_type == "stream",
    ).scalar()
    avg_rag_chunks = round(float(avg_chunks), 1) if avg_chunks else 0.0

    no_context_count = db.query(sqlfunc.count(models.AICallLog.id)).filter(
        models.AICallLog.date_creation >= from_date,
        models.AICallLog.call_type == "stream",
        models.AICallLog.rag_chunks_found == 0,
    ).scalar() or 0
    no_context_rate = round(no_context_count / total_calls * 100, 1) if total_calls > 0 else 0.0

    daily_rows = db.query(
        sqlfunc.date_trunc("day", models.AICallLog.date_creation).label("day"),
        sqlfunc.avg(models.AICallLog.latency_ms).label("avg_ms"),
        sqlfunc.count(models.AICallLog.id).label("calls"),
    ).filter(
        models.AICallLog.date_creation >= from_date,
        models.AICallLog.call_type == "stream",
        models.AICallLog.success == True,
    ).group_by("day").order_by("day").all()

    latency_trend = [
        {"name": f"{r.day.day} {r.day.strftime('%b')}", "latence_ms": round(float(r.avg_ms)), "appels": r.calls}
        for r in daily_rows if r.day and r.avg_ms
    ]

    model_row = db.query(models.AICallLog.model_name, sqlfunc.count(models.AICallLog.id).label("cnt")).filter(
        models.AICallLog.date_creation >= from_date,
        models.AICallLog.call_type == "stream",
        models.AICallLog.model_name.isnot(None),
    ).group_by(models.AICallLog.model_name).order_by(sqlfunc.count(models.AICallLog.id).desc()).first()
    model_name = model_row.model_name if model_row else None

    alerts = []
    if avg_latency_ms:
        if avg_latency_ms > 10000:
            alerts.append({"level": "critical", "metric": "latency", "message": f"Latence IA critique : {avg_latency_ms}ms en moyenne", "value": avg_latency_ms, "threshold": 10000})
        elif avg_latency_ms > 5000:
            alerts.append({"level": "warning", "metric": "latency", "message": f"Latence IA élevée : {avg_latency_ms}ms en moyenne", "value": avg_latency_ms, "threshold": 5000})
    if error_rate > 15:
        alerts.append({"level": "critical", "metric": "error_rate", "message": f"Taux d'erreur IA critique : {error_rate}%", "value": error_rate, "threshold": 15})
    elif error_rate > 5:
        alerts.append({"level": "warning", "metric": "error_rate", "message": f"Taux d'erreur IA élevé : {error_rate}%", "value": error_rate, "threshold": 5})
    if no_context_rate > 70 and total_calls >= 5:
        alerts.append({"level": "warning", "metric": "rag_quality", "message": f"{no_context_rate}% des questions sans contexte base de connaissances", "value": no_context_rate, "threshold": 70})

    return {
        "total_calls": total_calls,
        "error_rate": error_rate,
        "avg_latency_ms": avg_latency_ms,
        "avg_rag_chunks": avg_rag_chunks,
        "no_context_rate": no_context_rate,
        "latency_trend": latency_trend,
        "alerts": alerts,
        "model_name": model_name,
    }
