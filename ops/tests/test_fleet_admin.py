"""Tests de la page de gestion de flotte (ops/fleet_admin.py) — LOCALE UNIQUEMENT, cf. son
docstring et ops/README.md pour les garde-fous (jamais exposée au-delà de 127.0.0.1).

load_fleet_data() est le coeur de lecture, pure côté logique (pas de FastAPI, pas de HTML) —
testée directement. La route "/" est testée séparément via FastAPI TestClient (un vrai appel
HTTP en mémoire, pas de serveur réseau réel) pour vérifier que le rendu HTML ne plante pas et
contient les informations attendues.

Lancer : cd ops && pip install -r requirements-dev.txt && pytest
"""
from unittest import mock

import pytest
from fastapi.testclient import TestClient

import db
import fleet_admin
import render_client


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_instances.db")
    db.init_db()


@pytest.fixture
def render_mock():
    with mock.patch.object(fleet_admin, "render") as render_mock:
        render_mock.RenderAPIError = render_client.RenderAPIError
        render_mock.ensure_configured.return_value = None
        render_mock.list_services.return_value = []
        render_mock.list_postgres_instances.return_value = []
        yield render_mock


def _insert(*, slug, client_name="Client", statut="active", **extra):
    db.insert_instance(client_name=client_name, slug=slug, statut=statut, **extra)


def test_load_fleet_data_degrades_gracefully_without_render_api_key(monkeypatch):
    """RENDER_API_KEY absente/API injoignable : la page reste utilisable en local-only,
    juste sans croisement Render — ne doit jamais planter toute la lecture."""
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    _insert(slug="acme", client_name="Acme", plan_tarifaire="starter")

    data = fleet_admin.load_fleet_data(check_health=False)

    assert data.render_available is False
    assert len(data.instances) == 1
    assert data.instances[0].slug == "acme"
    assert data.instances[0].plan == "starter"
    assert data.instances[0].render_dashboard_backend is None
    assert data.instances[0].render_resource_missing is False  # jamais signalé "manquant" si le croisement est désactivé
    assert data.orphans == []


def test_load_fleet_data_cross_references_render_resources(render_mock):
    _insert(
        slug="acme", client_name="Acme", plan_tarifaire="starter",
        render_backend_service_id="srv-1", render_frontend_service_id="srv-2", render_database_id="pg-1",
    )
    render_mock.list_services.return_value = [
        {"id": "srv-1", "name": "smartticket-acme-x-backend", "type": "web_service", "dashboardUrl": "https://dashboard.render.com/web/srv-1"},
        {"id": "srv-2", "name": "smartticket-acme-x-frontend", "type": "web_service", "dashboardUrl": "https://dashboard.render.com/web/srv-2"},
    ]
    render_mock.list_postgres_instances.return_value = [
        {"id": "pg-1", "name": "smartticket-acme-x-postgres", "status": "available", "dashboardUrl": "https://dashboard.render.com/d/pg-1"},
    ]

    data = fleet_admin.load_fleet_data(check_health=False)

    assert data.render_available is True
    instance = data.instances[0]
    assert instance.render_resource_missing is False
    assert instance.render_dashboard_backend == "https://dashboard.render.com/web/srv-1"
    assert instance.render_dashboard_frontend == "https://dashboard.render.com/web/srv-2"
    assert instance.render_dashboard_postgres == "https://dashboard.render.com/d/pg-1"
    assert data.orphans == []


def test_load_fleet_data_flags_missing_render_resource(render_mock):
    """La ligne locale référence un backend qui n'apparaît PLUS côté Render (supprimé à la
    main sur le dashboard, ou orphelin d'un rollback incomplet) — doit être signalé, pas
    juste silencieusement ignoré."""
    _insert(slug="acme", client_name="Acme", render_backend_service_id="srv-gone")
    render_mock.list_services.return_value = []  # srv-gone n'existe plus côté Render
    render_mock.list_postgres_instances.return_value = []

    data = fleet_admin.load_fleet_data(check_health=False)

    assert data.instances[0].render_resource_missing is True


def test_load_fleet_data_finds_orphan_render_resources(render_mock):
    """Une ressource Render existe mais AUCUNE ligne locale ne la référence — même logique
    que audit_render_resources.py, exposée ici pour l'affichage web."""
    _insert(slug="acme", client_name="Acme", render_backend_service_id="srv-known")
    render_mock.list_services.return_value = [
        {"id": "srv-known", "name": "smartticket-acme-x-backend", "type": "web_service", "dashboardUrl": "https://dashboard.render.com/web/srv-known"},
        {"id": "srv-orphan", "name": "smartticket-test-old-backend", "type": "web_service", "dashboardUrl": "https://dashboard.render.com/web/srv-orphan"},
    ]
    render_mock.list_postgres_instances.return_value = []

    data = fleet_admin.load_fleet_data(check_health=False)

    assert len(data.orphans) == 1
    assert data.orphans[0]["id"] == "srv-orphan"
    assert data.orphans[0]["dashboard"] == "https://dashboard.render.com/web/srv-orphan"


def test_health_check_reports_ok_and_unreachable(monkeypatch):
    ok_response = mock.Mock(ok=True, status_code=200)
    monkeypatch.setattr(fleet_admin.requests, "get", mock.Mock(return_value=ok_response))
    assert fleet_admin._health_check("https://example.onrender.com") == ("ok", "HTTP 200")

    monkeypatch.setattr(
        fleet_admin.requests, "get",
        mock.Mock(side_effect=fleet_admin.requests.exceptions.ConnectionError("refused")),
    )
    status, detail = fleet_admin._health_check("https://example.onrender.com")
    assert status == "unreachable"
    assert "refused" in detail

    # Pas d'URL du tout (instance jamais arrivée à 'active') : ne doit pas planter, ni
    # tenter le moindre appel réseau.
    assert fleet_admin._health_check("") == ("non_verifie", "URL absente")


def test_index_route_renders_html_without_crashing(monkeypatch):
    """Bout en bout via FastAPI TestClient (appel HTTP en mémoire, pas de serveur réseau) —
    vérifie que la route réelle assemble données + template sans planter."""
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    _insert(slug="acme", client_name="Acme Corp", statut="active", plan_tarifaire="starter")
    _insert(slug="beta", client_name="Beta Inc", statut="provisioning")

    client = TestClient(fleet_admin.app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Acme Corp" in response.text
    assert "Beta Inc" in response.text
    assert "RENDER_API_KEY absente" in response.text
