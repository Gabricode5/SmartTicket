"""Tests du rollback best-effort de provision() sur échec partiel — cf.
ops/provision_client.py::_rollback().

Seule couverture de test existante pour ops/ à ce jour : ce dossier manipule des ressources
Render facturées, et le rollback est du code qui ne s'exécute QUE quand tout va déjà mal — sans
test durable, on ne découvre qu'il est cassé que le jour où on compte vraiment dessus.

Lancer : cd ops && pip install -r requirements-dev.txt && pytest
"""
from unittest import mock

import pytest

import db
import provision_client


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Chaque test tourne sur son propre fichier SQLite jetable — jamais le vrai
    ops/instances.db du poste (qui contiendrait de vraies instances clientes)."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_instances.db")


@pytest.fixture
def render_mock():
    with mock.patch.object(provision_client, "render") as render_mock:
        yield render_mock


@pytest.fixture
def notify_mock():
    with mock.patch.object(provision_client, "notify") as notify_mock:
        yield notify_mock


def _mock_common_steps(render_mock, *, postgres_id: str):
    render_mock.get_owner_id.return_value = "owner-1"
    render_mock.create_postgres.return_value = {"id": postgres_id}
    render_mock.get_postgres_connection_info.return_value = {"internalConnectionString": "postgres://x"}
    render_mock.wait_for_deploy_live.return_value = True


def _mock_frontend_creation_failure(render_mock, *, backend_id: str):
    """Backend créé avec succès, la création du frontend échoue — le point d'échec utilisé
    par tous les tests de rollback ci-dessous : il garantit 2 ressources déjà créées
    (Postgres + backend) au moment où provision() doit déclencher le rollback."""
    render_mock.create_web_service.side_effect = [
        {"id": backend_id, "serviceDetails": {"url": f"https://{backend_id}.onrender.com"}},
        RuntimeError("Render 500: échec de création du frontend"),
    ]


def test_full_success_never_calls_delete_and_marks_instance_active(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-1")
    render_mock.create_web_service.side_effect = [
        {"id": "backend-1", "serviceDetails": {"url": "https://backend-1.onrender.com"}},
        {"id": "frontend-1", "serviceDetails": {"url": "https://frontend-1.onrender.com"}},
    ]
    notify_mock.send_welcome_email.return_value = True

    result = provision_client.provision(
        client_name="Acme", slug="acme-success", postgres_plan="starter", admin_email="a@acme.com",
    )

    assert result.status == "active"
    render_mock.delete_resources.assert_not_called()
    row = db.get_instance("acme-success")
    assert row["statut"] == "active"
    assert row["render_backend_service_id"] == "backend-1"
    assert row["render_frontend_service_id"] == "frontend-1"


def test_partial_failure_rolls_back_in_reverse_order_and_frees_slug(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-2")
    _mock_frontend_creation_failure(render_mock, backend_id="backend-2")
    render_mock.delete_resources.return_value = []  # rollback réussi à 100%

    result = provision_client.provision(
        client_name="Acme2", slug="acme-rollback-ok", postgres_plan="starter", admin_email="a@acme2.com",
    )

    assert result.status == "failed"
    assert "ROLLBACK INCOMPLET" not in result.error

    # Postgres créé en premier, backend en second → suppression dans l'ordre INVERSE :
    # backend d'abord, Postgres ensuite.
    (called_resources,), _ = render_mock.delete_resources.call_args
    assert [label for label, _, _ in called_resources] == ["service backend", "base Postgres"]
    assert [rid for _, _, rid in called_resources] == ["backend-2", "pg-2"]

    assert db.get_instance("acme-rollback-ok") is None
    assert not db.slug_exists("acme-rollback-ok")


def test_incomplete_rollback_burns_the_slug_and_reports_orphans(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-3")
    _mock_frontend_creation_failure(render_mock, backend_id="backend-3")
    render_mock.delete_resources.return_value = [("service backend", "service", "backend-3")]

    result = provision_client.provision(
        client_name="Acme3", slug="acme-rollback-fail", postgres_plan="starter", admin_email="a@acme3.com",
    )

    assert result.status == "failed"
    assert "ROLLBACK INCOMPLET" in result.error
    assert "backend-3" in result.error

    row = db.get_instance("acme-rollback-fail")
    assert row is not None, "la ligne doit être CONSERVÉE (pas supprimée) après un rollback incomplet"
    assert row["statut"] == "failed"
    assert "backend-3" in row["notes"]


def test_burned_slug_blocks_retry_without_touching_render_again(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-4")
    _mock_frontend_creation_failure(render_mock, backend_id="backend-4")
    render_mock.delete_resources.return_value = [("service backend", "service", "backend-4")]

    first = provision_client.provision(
        client_name="Acme4", slug="acme-burned", postgres_plan="starter", admin_email="a@acme4.com",
    )
    assert first.status == "failed"
    assert db.slug_exists("acme-burned")

    retry = provision_client.provision(
        client_name="Acme4", slug="acme-burned", postgres_plan="starter", admin_email="a@acme4.com",
    )

    assert retry.status == "failed"
    assert "existe déjà" in retry.error
    # Un seul appel Render au total (celui du premier essai) : le retry n'a rien recréé.
    render_mock.create_postgres.assert_called_once()
