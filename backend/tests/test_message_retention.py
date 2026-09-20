"""Tests de la purge par rétention des messages de chat (minimisation RGPD, indépendante de
la suppression de compte/session déjà couverte par purge_soft_deleted, cf. main.py).
"""
import secrets
from datetime import datetime, timedelta

import models
from main import purge_old_messages

_TEST_PASSWORD = secrets.token_urlsafe(16)


def _make_user(db_session, *, email: str) -> models.Utilisateur:
    role_row = db_session.query(models.Role).filter_by(nom_role="user").first()
    user = models.Utilisateur(
        username=email.split("@")[0], email=email, password_hash="x", id_role=role_row.id, email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_session(db_session, user: models.Utilisateur) -> models.ChatSession:
    session = models.ChatSession(id_utilisateur=user.id, status="open")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _make_message(db_session, session: models.ChatSession, *, age_days: int, contenu: str) -> models.ChatMessage:
    message = models.ChatMessage(
        id_session=session.id, type_envoyeur="user", contenu=contenu,
        date_creation=datetime.utcnow() - timedelta(days=age_days),
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


class TestMessageRetentionPurge:
    def test_old_message_is_deleted(self, db_session):
        user = _make_user(db_session, email="retention-old@example.com")
        session = _make_session(db_session, user)
        old = _make_message(db_session, session, age_days=400, contenu="vieux message")
        old_id = old.id  # capturé avant purge : la ligne va être supprimée par une autre session

        purge_old_messages(retention_days=365)

        db_session.expire_all()
        assert db_session.query(models.ChatMessage).filter_by(id=old_id).first() is None

    def test_recent_message_is_kept(self, db_session):
        user = _make_user(db_session, email="retention-recent@example.com")
        session = _make_session(db_session, user)
        recent = _make_message(db_session, session, age_days=10, contenu="message récent")

        purge_old_messages(retention_days=365)

        db_session.expire_all()
        assert db_session.query(models.ChatMessage).filter_by(id=recent.id).first() is not None

    def test_session_is_not_deleted_when_its_messages_are_purged(self, db_session):
        user = _make_user(db_session, email="retention-session@example.com")
        session = _make_session(db_session, user)
        _make_message(db_session, session, age_days=400, contenu="vieux message")

        purge_old_messages(retention_days=365)

        db_session.expire_all()
        assert db_session.query(models.ChatSession).filter_by(id=session.id).first() is not None
