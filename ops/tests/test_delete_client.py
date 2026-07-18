"""Tests de delete_client.py — en particulier l'ordre des opérations entre la suppression
des ressources Render et la modification d'instances.db.

Bug réel du 2026-07-16 : une RENDER_API_KEY manquante faisait échouer les 3 suppressions
Render (backend, frontend, Postgres), mais le script retirait quand même la ligne
d'instances.db juste après — 3 ressources restées facturées, plus aucune trace dans le
registre pour les retrouver, ni même pour relancer leur suppression. Cf. render_client.py
(ensure_configured()) et delete_client.py pour le correctif.

Lancer : cd ops && pip install -r requirements-dev.txt && pytest
"""
from unittest import mock

import pytest

import db
import delete_client
import render_client


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Jamais le vrai ops/instances.db du poste — cf. test_provision_rollback.py."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_instances.db")
    db.init_db()


@pytest.fixture
def render_mock():
    with mock.patch.object(delete_client, "render") as render_mock:
        # Par défaut, la validation fail-fast passe et le mock RenderAPIError se comporte
        # comme la vraie classe (nécessaire pour un `except render.RenderAPIError` réaliste
        # dans le code testé, cf. test_render_client.py pour le même besoin).
        render_mock.RenderAPIError = render_client.RenderAPIError
        render_mock.ensure_configured.return_value = None
        yield render_mock


def _insert_instance(*, slug: str, statut: str = "active"):
    db.insert_instance(
        client_name=f"Client {slug}", slug=slug, statut=statut,
        render_backend_service_id=f"backend-{slug}",
        render_frontend_service_id=f"frontend-{slug}",
        render_database_id=f"pg-{slug}",
    )


def _run(monkeypatch, *args: str) -> int:
    monkeypatch.setattr("sys.argv", ["delete_client.py", *args])
    return delete_client.main()


def test_full_success_removes_the_row(render_mock, monkeypatch):
    _insert_instance(slug="acme-ok")
    render_mock.delete_resources.return_value = []  # tout supprimé avec succès

    exit_code = _run(monkeypatch, "--slug", "acme-ok", "--yes")

    assert exit_code == 0
    assert db.get_instance("acme-ok") is None


def test_keep_row_on_success_marks_supprimee(render_mock, monkeypatch):
    _insert_instance(slug="acme-keep")
    render_mock.delete_resources.return_value = []

    exit_code = _run(monkeypatch, "--slug", "acme-keep", "--yes", "--keep-row")

    assert exit_code == 0
    row = db.get_instance("acme-keep")
    assert row is not None
    assert row["statut"] == "supprimee"


class TestPartialDeletionFailureKeepsTheRow:
    """Le coeur du bug : tant qu'une ressource Render n'a pas pu être supprimée, la ligne
    DOIT rester dans instances.db avec les IDs orphelins — sans ça, ces ressources
    continuent d'être facturées sans qu'aucune trace ne permette de les retrouver."""

    def test_row_survives_with_orphan_ids_in_notes(self, render_mock, monkeypatch):
        _insert_instance(slug="acme-fail")
        render_mock.delete_resources.return_value = [
            ("service backend", "service", "backend-acme-fail"),
            ("service frontend", "service", "frontend-acme-fail"),
            ("base Postgres", "postgres", "pg-acme-fail"),
        ]

        exit_code = _run(monkeypatch, "--slug", "acme-fail", "--yes")

        assert exit_code == 1
        row = db.get_instance("acme-fail")
        assert row is not None, "la ligne doit être CONSERVÉE — c'est le seul moyen de retrouver les ressources orphelines"
        assert row["statut"] == "deletion_failed"
        assert "backend-acme-fail" in row["notes"]
        assert "frontend-acme-fail" in row["notes"]
        assert "pg-acme-fail" in row["notes"]

    def test_partial_failure_also_keeps_the_row_even_with_keep_row_not_passed(self, render_mock, monkeypatch):
        """--keep-row ne doit rien changer au comportement en échec : la ligne reste de
        toute façon, --keep-row ne concerne que le cas de succès complet."""
        _insert_instance(slug="acme-fail2")
        render_mock.delete_resources.return_value = [("base Postgres", "postgres", "pg-acme-fail2")]

        exit_code = _run(monkeypatch, "--slug", "acme-fail2", "--yes")

        assert exit_code == 1
        assert db.get_instance("acme-fail2") is not None


class TestRenderApiKeyMissingFailsBeforeAnyDbChange:
    """Bug réel : RENDER_API_KEY absente du shell → les 3 suppressions Render échouaient
    (chacune levant RenderAPIError), mais le script retirait quand même la ligne juste
    après. render.ensure_configured() doit maintenant échouer AVANT le moindre appel à
    delete_resources() et avant toute modification d'instances.db."""

    def test_missing_api_key_leaves_the_row_completely_untouched(self, monkeypatch):
        _insert_instance(slug="acme-nokey", statut="active")
        # PAS de render_mock ici : on veut le vrai render_client.ensure_configured(), pour
        # vérifier le comportement réel rapporté par l'utilisateur, pas une simulation.
        monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
        with mock.patch.object(render_client, "delete_resources") as delete_resources_spy:
            exit_code = _run(monkeypatch, "--slug", "acme-nokey", "--yes")
            delete_resources_spy.assert_not_called()

        assert exit_code == 1
        row = db.get_instance("acme-nokey")
        assert row is not None
        # Complètement INTACTE — pas seulement présente, mais jamais touchée : ni statut
        # basculé sur 'deletion_failed', ni notes modifiées, ni IDs perdus.
        assert row["statut"] == "active"
        assert row["notes"] is None

    def test_dry_run_does_not_require_render_api_key(self, monkeypatch):
        """--dry-run ne fait aucun appel Render : ne doit jamais exiger RENDER_API_KEY,
        exactement comme le --dry-run de provision_client.py."""
        _insert_instance(slug="acme-dry")
        monkeypatch.setattr(render_client, "RENDER_API_KEY", None)

        exit_code = _run(monkeypatch, "--slug", "acme-dry", "--dry-run")

        assert exit_code == 0
        assert db.get_instance("acme-dry") is not None
