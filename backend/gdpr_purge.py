"""Purge ciblée des entrées knowledge_base dérivées d'un ticket (INDEX_CLOSED_TICKETS,
cf. routers/sessions.py::close_session) -- RGPD art. 17 (droit à l'effacement).

Module séparé plutôt qu'ajouté à main.py : routers/users.py doit pouvoir appeler cette purge
directement depuis DELETE /users/{id}, et main.py importe déjà tous les routers au chargement
-- un import en retour depuis routers/users.py créerait un cycle.

purge_soft_deleted() (main.py) n'a PAS besoin d'appeler ce module : ses DELETE bulk sur
ChatSession/Utilisateur déclenchent déjà la cascade PostgreSQL (knowledge_base.source_user_id/
source_session_id sont ON DELETE CASCADE), dans la même transaction, sans code applicatif
supplémentaire. Ce module ne sert donc que le cas où l'effacement RGPD doit être immédiat
sans attendre un hard-delete -- aujourd'hui uniquement DELETE /users/{id} (soft-delete only).
"""

from sqlalchemy.orm import Session

import models


def purge_knowledge_base_for_user(db: Session, user_id: int) -> int:
    return db.query(models.KnowledgeBase).filter(models.KnowledgeBase.source_user_id == user_id).delete(synchronize_session=False)


def purge_knowledge_base_for_session(db: Session, session_id: int) -> int:
    return db.query(models.KnowledgeBase).filter(models.KnowledgeBase.source_session_id == session_id).delete(synchronize_session=False)
