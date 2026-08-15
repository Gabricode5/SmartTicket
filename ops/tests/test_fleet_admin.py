"""Tests de la page de gestion de flotte (ops/fleet_admin.py) — LOCALE UNIQUEMENT, cf. son
docstring et ops/README.md pour les garde-fous (jamais exposée au-delà de 127.0.0.1).

load_fleet_data() est le coeur de lecture, pure côté logique (pas de FastAPI, pas de HTML) —
testée directement. La route "/" est testée séparément via FastAPI TestClient (un vrai appel
HTTP en mémoire, pas de serveur réseau réel) pour vérifier que le rendu HTML ne plante pas et
contient les informations attendues.

La suspension/réactivation (Partie B.2) est en plus couverte par un vrai serveur HTTP local
(fixture `fake_instance_server`, http.server standard) qui simule le coupe-circuit
d'abonnement d'une vraie instance (GET/PUT /v1/instance/subscription-status protégé par
X-Vendor-Key, cf. backend/routers/instance.py) — pas juste des mocks, un aller-retour HTTP
réel en localhost pour le scénario suspend -> 402 -> reactivate demandé.

Lancer : cd ops && pip install -r requirements-dev.txt && pytest
"""
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

import pytest
from fastapi.testclient import TestClient

import db
import delete_client
import fleet_admin
import provision_client
import render_client


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_instances.db")
    db.init_db()


@pytest.fixture(autouse=True)
def clear_provision_jobs():
    """_provision_jobs est un dict au niveau du module (délibérément — cf. docstring de
    fleet_admin.py) : sans ce nettoyage, un job laissé par un test polluerait les suivants."""
    fleet_admin._provision_jobs.clear()
    yield
    fleet_admin._provision_jobs.clear()


@pytest.fixture
def synchronous_background_thread(monkeypatch):
    """Remplace threading.Thread par une exécution SYNCHRONE de la cible — pour tester
    _run_provision_job() de façon déterministe, sans race condition/sleep, sans jamais
    lancer un vrai thread. La route elle-même ne sait pas que ce n'est pas un vrai thread."""
    class ImmediateThread:
        def __init__(self, target=None, kwargs=None, **_ignored):
            self._target = target
            self._kwargs = kwargs or {}

        def start(self):
            self._target(**self._kwargs)

    monkeypatch.setattr(fleet_admin.threading, "Thread", ImmediateThread)


@pytest.fixture
def provision_mock():
    with mock.patch.object(fleet_admin, "provision_client") as provision_mock:
        yield provision_mock


@pytest.fixture
def render_mock():
    with mock.patch.object(fleet_admin, "render") as render_mock:
        render_mock.RenderAPIError = render_client.RenderAPIError
        render_mock.ensure_configured.return_value = None
        render_mock.list_services.return_value = []
        render_mock.list_postgres_instances.return_value = []
        yield render_mock


@pytest.fixture
def delete_client_mock():
    """Mocke le MODULE delete_client tel qu'importé par fleet_admin — vérifie que la route
    de suppression appelle delete_client.delete_instance() (la même fonction que la CLI,
    déjà testée en détail dans test_delete_client.py) sans en réimplémenter la logique ici."""
    with mock.patch.object(fleet_admin, "delete_client") as delete_client_mock:
        yield delete_client_mock


def _insert(*, slug, client_name="Client", statut="active", **extra):
    db.insert_instance(client_name=client_name, slug=slug, statut=statut, **extra)


class _FakeInstanceHandler(BaseHTTPRequestHandler):
    """Simule backend/routers/instance.py : GET/PUT /v1/instance/subscription-status,
    protégé par X-Vendor-Key, statut partagé via self.server.state."""

    def _authorized(self) -> bool:
        return self.headers.get("X-Vendor-Key") == self.server.vendor_key  # type: ignore[attr-defined]

    def do_GET(self):
        if self.path != "/v1/instance/subscription-status":
            self.send_response(404); self.end_headers(); return
        if not self._authorized():
            self.send_response(403); self.end_headers(); return
        body = json.dumps({"status": self.server.state["status"], "reason": None}).encode()  # type: ignore[attr-defined]
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        if self.path != "/v1/instance/subscription-status":
            self.send_response(404); self.end_headers(); return
        if not self._authorized():
            self.send_response(403); self.end_headers(); return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        self.server.state["status"] = payload["status"]  # type: ignore[attr-defined]
        body = json.dumps({"status": payload["status"], "reason": payload.get("reason")}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_instance_server():
    """Un vrai serveur HTTP en 127.0.0.1 (port éphémère), pas un mock — pour vérifier le
    scénario demandé (suspendre -> 402 -> réactiver) sur un aller-retour réseau réel."""
    server = HTTPServer(("127.0.0.1", 0), _FakeInstanceHandler)
    server.vendor_key = "test-vendor-key"  # type: ignore[attr-defined]
    server.state = {"status": "active"}  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=2)


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


# --- Partie B.2 : suspendre / réactiver via le coupe-circuit d'abonnement existant ---

def test_subscription_status_check_reports_real_status(monkeypatch):
    response = mock.Mock(ok=True, json=lambda: {"status": "suspended", "updated_at": "2026-08-01T00:00:00+00:00"})
    monkeypatch.setattr(fleet_admin.requests, "get", mock.Mock(return_value=response))

    status, detail, updated_at = fleet_admin._subscription_status_check("https://instance.example", "vk-1")

    assert status == "suspended"
    assert detail == ""
    assert updated_at == "2026-08-01T00:00:00+00:00"


def test_subscription_status_check_reports_unknown_when_instance_unreachable(monkeypatch):
    """Instance down/injoignable : 'unknown', jamais une exception qui remonte et casse la
    page — exigence explicite de la Partie B.2."""
    monkeypatch.setattr(
        fleet_admin.requests, "get",
        mock.Mock(side_effect=fleet_admin.requests.exceptions.ConnectionError("refused")),
    )

    status, detail, updated_at = fleet_admin._subscription_status_check("https://instance.example", "vk-1")

    assert status == "unknown"
    assert "refused" in detail
    assert updated_at is None


def test_subscription_status_update_never_raises_and_reports_real_outcome(monkeypatch):
    monkeypatch.setattr(
        fleet_admin.requests, "put",
        mock.Mock(side_effect=fleet_admin.requests.exceptions.Timeout("timed out")),
    )

    ok, message = fleet_admin._subscription_status_update("https://instance.example", "vk-1", status="suspended")

    assert ok is False
    assert "timed out" in message


def test_load_fleet_data_skips_subscription_check_for_non_active_instances(monkeypatch):
    """Une instance encore en 'provisioning' n'a pas de backend joignable — inutile (et
    trompeur) de tenter un GET dessus."""
    get_mock = mock.Mock()
    monkeypatch.setattr(fleet_admin.requests, "get", get_mock)
    _insert(slug="acme", statut="provisioning", vendor_key="vk-1", backend_url="https://instance.example")

    data = fleet_admin.load_fleet_data(check_health=False)

    assert data.instances[0].subscription_status == "not_applicable"
    get_mock.assert_not_called()


def test_load_fleet_data_flags_missing_vendor_key(monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    _insert(slug="acme", statut="active", backend_url="https://instance.example")  # pas de vendor_key

    data = fleet_admin.load_fleet_data(check_health=False, check_subscription=False)

    assert data.instances[0].can_manage_subscription is False
    assert data.instances[0].subscription_status == "unknown"


def test_suspend_route_rejects_mismatched_slug_confirmation_without_calling_the_instance(monkeypatch):
    put_mock = mock.Mock()
    monkeypatch.setattr(fleet_admin.requests, "put", put_mock)
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    _insert(slug="acme", statut="active", backend_url="https://instance.example", vendor_key="vk-1")

    client = TestClient(fleet_admin.app)
    response = client.post("/instances/acme/suspend", data={"confirm_slug": "not-acme"})

    assert response.status_code == 200
    assert "Confirmation invalide" in response.text
    put_mock.assert_not_called()


def test_suspend_route_disabled_when_vendor_key_missing(monkeypatch):
    put_mock = mock.Mock()
    monkeypatch.setattr(fleet_admin.requests, "put", put_mock)
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    _insert(slug="acme", statut="active", backend_url="https://instance.example")  # pas de vendor_key

    client = TestClient(fleet_admin.app)
    index_response = client.get("/")
    assert "vendor_key absente — suspension impossible" in index_response.text

    action_response = client.post("/instances/acme/suspend", data={"confirm_slug": "acme"})
    assert "vendor_key ou URL backend absente" in action_response.text
    put_mock.assert_not_called()


def test_vendor_key_never_appears_in_rendered_html(monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    monkeypatch.setattr(fleet_admin.requests, "get", mock.Mock(side_effect=fleet_admin.requests.exceptions.ConnectionError()))
    _insert(slug="acme", statut="active", backend_url="https://instance.example", vendor_key="super-secret-vendor-key")

    client = TestClient(fleet_admin.app)
    response = client.get("/")

    assert "super-secret-vendor-key" not in response.text


def test_suspend_then_reactivate_end_to_end_over_real_http(monkeypatch, fake_instance_server):
    """Le scénario exact demandé : suspendre une instance -> son subscription-status passe
    à 'suspended' (ce qui déclenche le 402 sur /v1/* côté backend réel, hors scope ici, déjà
    couvert par les tests backend existants) -> réactiver -> retour à 'active'. Aller-retour
    HTTP réel sur 127.0.0.1, pas mocké."""
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    base_url = f"http://127.0.0.1:{fake_instance_server.server_address[1]}"
    _insert(slug="acme", statut="active", backend_url=base_url, vendor_key="test-vendor-key")

    client = TestClient(fleet_admin.app)

    before = client.get("/")
    assert "sub-active" in before.text

    suspend_resp = client.post("/instances/acme/suspend", data={"confirm_slug": "acme"})
    assert "action réussie" in suspend_resp.text
    assert fake_instance_server.state["status"] == "suspended"
    assert "sub-suspended" in suspend_resp.text  # re-GET après action, pas supposé

    reactivate_resp = client.post("/instances/acme/reactivate", data={"confirm_slug": "acme"})
    assert "action réussie" in reactivate_resp.text
    assert fake_instance_server.state["status"] == "active"
    assert "sub-active" in reactivate_resp.text


# --- Partie B.2bis.2 : rappel de facturation ("suspendue depuis X jours") ---

def test_days_since_computes_from_iso_timestamp():
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert fleet_admin._days_since(ten_days_ago) == 10


def test_days_since_handles_z_suffix_and_missing_or_invalid_input():
    assert fleet_admin._days_since("2026-08-01T00:00:00Z") is not None  # ne plante pas sur le 'Z'
    assert fleet_admin._days_since(None) is None
    assert fleet_admin._days_since("n'importe quoi") is None


def test_load_fleet_data_computes_since_days_only_for_suspended_instances(monkeypatch):
    """updated_at vient de models.InstanceSubscription (déjà auto-maintenue côté backend,
    cf. backend/models.py) — pas d'une nouvelle colonne locale."""
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    _insert(slug="suspended-one", statut="active", backend_url="https://instance.example", vendor_key="vk-1")
    response = mock.Mock(ok=True, json=lambda: {"status": "suspended", "updated_at": five_days_ago})
    monkeypatch.setattr(fleet_admin.requests, "get", mock.Mock(return_value=response))

    data = fleet_admin.load_fleet_data(check_health=False)

    assert data.instances[0].subscription_since_days == 5


def test_load_fleet_data_since_days_is_none_when_active(monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    _insert(slug="acme", statut="active", backend_url="https://instance.example", vendor_key="vk-1")
    response = mock.Mock(ok=True, json=lambda: {"status": "active", "updated_at": datetime.now(timezone.utc).isoformat()})
    monkeypatch.setattr(fleet_admin.requests, "get", mock.Mock(return_value=response))

    data = fleet_admin.load_fleet_data(check_health=False)

    assert data.instances[0].subscription_since_days is None


def test_billing_reminder_shown_for_a_long_suspended_instance(monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    seventeen_days_ago = (datetime.now(timezone.utc) - timedelta(days=17)).isoformat()
    _insert(slug="acme", statut="active", client_name="Acme Corp", backend_url="https://instance.example", vendor_key="vk-1")
    response = mock.Mock(ok=True, json=lambda: {"status": "suspended", "updated_at": seventeen_days_ago})
    monkeypatch.setattr(fleet_admin.requests, "get", mock.Mock(return_value=response))

    client = TestClient(fleet_admin.app)
    response_html = client.get("/").text

    assert "suspendue depuis 17 jour" in response_html
    assert "facturation Render TOUJOURS ACTIVE" in response_html


# --- Partie B.2bis.1 : suppression définitive, double confirmation ---

def test_delete_route_rejects_mismatched_slug_without_calling_delete_instance(delete_client_mock, render_mock):
    _insert(slug="acme", statut="active")
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/acme/delete", data={"confirm_slug": "not-acme", "confirm_destruction": "yes"})

    assert "Confirmation invalide" in response.text
    delete_client_mock.delete_instance.assert_not_called()


def test_delete_route_rejects_missing_checkbox_confirmation(delete_client_mock, render_mock):
    """Garde-fou EN PLUS de la saisie du slug — plus strict que suspendre/réactiver, cf.
    consigne explicite de la Partie B.2bis (action irréversible)."""
    _insert(slug="acme", statut="active")
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/acme/delete", data={"confirm_slug": "acme"})  # pas de confirm_destruction

    assert "Case de confirmation non cochée" in response.text
    delete_client_mock.delete_instance.assert_not_called()


def test_delete_route_calls_delete_instance_with_the_right_slug(delete_client_mock, render_mock):
    """Vérifie que fleet_admin appelle delete_client.delete_instance() — MÊME fonction que
    la CLI (déjà testée en détail dans test_delete_client.py), rien réimplémenté ici."""
    _insert(slug="acme", statut="active", client_name="Acme Corp")
    delete_client_mock.delete_instance.return_value = delete_client.DeleteResult(slug="acme", status="deleted")

    client = TestClient(fleet_admin.app)
    response = client.post("/instances/acme/delete", data={"confirm_slug": "acme", "confirm_destruction": "yes"})

    delete_client_mock.delete_instance.assert_called_once_with("acme")
    assert "action réussie" in response.text


def test_delete_route_removes_instance_from_list_on_real_success(render_mock, monkeypatch):
    """Bout en bout avec le VRAI delete_client.delete_instance() (seul render_client est
    mocké, pas delete_client) : l'instance doit réellement disparaître du registre ET de la
    liste re-affichée, pas juste être annoncée comme supprimée."""
    with mock.patch.object(delete_client, "render") as delete_render_mock:
        delete_render_mock.RenderAPIError = render_client.RenderAPIError
        delete_render_mock.ensure_configured.return_value = None
        delete_render_mock.delete_resources.return_value = []  # suppression Render réussie

        _insert(
            slug="acme", statut="active", client_name="Acme Corp",
            render_backend_service_id="srv-b", render_frontend_service_id="srv-f", render_database_id="pg-1",
        )

        client = TestClient(fleet_admin.app)
        response = client.post("/instances/acme/delete", data={"confirm_slug": "acme", "confirm_destruction": "yes"})

        assert "action réussie" in response.text
        assert "Acme Corp" not in response.text
        assert db.get_instance("acme") is None
        delete_render_mock.delete_resources.assert_called_once_with([
            ("service backend", "service", "srv-b"),
            ("service frontend", "service", "srv-f"),
            ("base Postgres", "postgres", "pg-1"),
        ])


def test_delete_route_reports_partial_failure_honestly(delete_client_mock, render_mock):
    """Ne JAMAIS afficher un succès quand delete_instance() rapporte un échec partiel
    (ligne conservée en 'deletion_failed', cf. delete_client.py) — même exigence que pour
    suspendre/réactiver."""
    _insert(slug="acme", statut="active", client_name="Acme Corp")
    delete_client_mock.delete_instance.return_value = delete_client.DeleteResult(
        slug="acme", status="failed", error="1 ressource(s) Render n'ont pas pu être supprimées : base Postgres (id=pg-1).",
    )

    client = TestClient(fleet_admin.app)
    response = client.post("/instances/acme/delete", data={"confirm_slug": "acme", "confirm_destruction": "yes"})

    assert "action réussie" not in response.text
    assert "pg-1" in response.text
    assert "Acme Corp" in response.text  # toujours dans la liste, pas de faux succès


def test_delete_action_offered_for_active_and_suspended_but_not_for_supprimee(monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    _insert(slug="acme-active", statut="active", client_name="Actif")
    _insert(slug="acme-failed", statut="failed", client_name="Echoue")
    _insert(slug="acme-gone", statut="supprimee", client_name="Deja Supprime")

    client = TestClient(fleet_admin.app)
    html = client.get("/").text

    assert html.count("Supprimer définitivement") == 2  # actif + échoué, pas le déjà-supprimé


def test_all_action_routes_are_actually_registered_as_post():
    """Garde-fou dédié et sans ambiguïté possible : énumère les routes RÉELLEMENT
    enregistrées sur l'app FastAPI (fleet_admin.app.routes), indépendamment de tout appel
    HTTP. Les tests *_route_* ci-dessus passent déjà par TestClient (qui dispatche via le
    vrai routeur ASGI, pas un raccourci vers delete_instance()/_subscription_status_update())
    et auraient donc déjà échoué en 404 si une route manquait — celui-ci rend l'enregistrement
    lui-même l'objet direct de l'assertion, pour qu'une régression future (route retirée par
    erreur, mal orthographiée, mauvaise méthode HTTP) soit signalée sans détour."""
    registered = {
        (route.path, method)
        for route in fleet_admin.app.routes
        for method in getattr(route, "methods", set())
    }
    for action in ("suspend", "reactivate", "delete"):
        assert (f"/instances/{{slug}}/{action}", "POST") in registered, f"route POST /instances/{{slug}}/{action} manquante"
    assert ("/instances/create", "POST") in registered, "route POST /instances/create manquante"


# --- Partie B.3 : création d'instance via provision() en tâche de fond ---

def test_slug_pattern_accepts_valid_and_rejects_invalid_slugs():
    assert fleet_admin._SLUG_PATTERN.match("acme-corp")
    assert fleet_admin._SLUG_PATTERN.match("acme123")
    assert not fleet_admin._SLUG_PATTERN.match("Acme-Corp")  # majuscules
    assert not fleet_admin._SLUG_PATTERN.match("-acme")  # tiret en tête
    assert not fleet_admin._SLUG_PATTERN.match("acme-")  # tiret en fin
    assert not fleet_admin._SLUG_PATTERN.match("acme_corp")  # underscore
    assert not fleet_admin._SLUG_PATTERN.match("")


def test_create_route_rejects_invalid_slug_format_without_starting_a_job(provision_mock, synchronous_background_thread):
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/create", data={
        "client_name": "Acme", "slug": "Not A Slug!", "admin_email": "a@acme.com", "postgres_plan": "basic_256mb",
    })

    assert "invalide" in response.text
    provision_mock.provision.assert_not_called()
    assert fleet_admin._provision_jobs == {}


def test_create_route_rejects_missing_required_fields(provision_mock, synchronous_background_thread):
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/create", data={
        "client_name": "   ", "slug": "acme", "admin_email": "a@acme.com", "postgres_plan": "basic_256mb",
    })

    assert "requis" in response.text
    provision_mock.provision.assert_not_called()


def test_create_route_rejects_slug_already_in_registry(provision_mock, synchronous_background_thread):
    """provision() referait cette vérification et refuserait de toute façon — celle-ci n'est
    qu'un retour immédiat côté formulaire, pour ne pas lancer un thread pour rien."""
    _insert(slug="acme", statut="active")
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/create", data={
        "client_name": "Acme Bis", "slug": "acme", "admin_email": "a@acme.com", "postgres_plan": "basic_256mb",
    })

    assert "existe déjà" in response.text
    provision_mock.provision.assert_not_called()


def test_create_route_calls_provision_with_the_right_arguments(provision_mock, synchronous_background_thread):
    """MÊME fonction que la CLI (provision_client.provision()), rien réimplémenté ici."""
    provision_mock.provision.return_value = provision_client.ProvisionResult(
        slug="acme", status="active", setup_url="https://smartticket-acme.onrender.com/setup?token=abc123",
        welcome_email_sent=True,
    )
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/create", data={
        "client_name": "Acme Corp", "slug": "acme", "admin_email": "a@acme.com", "postgres_plan": "basic_1gb",
    })

    provision_mock.provision.assert_called_once_with(
        client_name="Acme Corp", slug="acme", admin_email="a@acme.com", postgres_plan="basic_1gb",
    )
    assert "lancée en tâche de fond" in response.text
    # Grâce à synchronous_background_thread, le job est déjà terminé à ce stade.
    # (Chaîne précise, pas juste "job-succeeded" — cette sous-chaîne apparaît aussi dans le
    # <style> via le sélecteur CSS .job-succeeded, présent que le job existe ou non.)
    assert 'class="job-card job-succeeded"' in response.text
    assert "https://smartticket-acme.onrender.com/setup?token=abc123" in response.text
    assert "Email de bienvenue envoyé" in response.text


def test_create_job_reports_provision_failure_honestly_never_as_success(provision_mock, synchronous_background_thread):
    """Ne JAMAIS afficher un succès quand provision() rapporte un échec (rollback déjà géré
    par provision() elle-même, cf. provision_client.py) — même exigence que pour les autres
    actions de cette page."""
    provision_mock.provision.return_value = provision_client.ProvisionResult(
        slug="acme", status="failed", error="Erreur Render simulée : quota dépassé",
    )
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/create", data={
        "client_name": "Acme Corp", "slug": "acme", "admin_email": "a@acme.com", "postgres_plan": "basic_256mb",
    })

    assert 'class="job-card job-failed"' in response.text
    assert 'class="job-card job-succeeded"' not in response.text
    assert "Erreur Render simulée : quota dépassé" in response.text


def test_create_job_survives_an_unexpected_exception_from_provision(provision_mock, synchronous_background_thread):
    """Filet de sécurité : même si provision() levait une exception inattendue (elle ne
    devrait normalement jamais le faire), le job doit finir en 'failed' plutôt que de rester
    bloqué à 'running' pour toujours ou de faire planter le thread en silence."""
    provision_mock.provision.side_effect = RuntimeError("boom inattendu")
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/create", data={
        "client_name": "Acme Corp", "slug": "acme", "admin_email": "a@acme.com", "postgres_plan": "basic_256mb",
    })

    assert 'class="job-card job-failed"' in response.text
    assert "boom inattendu" in response.text


def test_create_job_never_exposes_vendor_key(provision_mock, synchronous_background_thread):
    provision_mock.provision.return_value = provision_client.ProvisionResult(
        slug="acme", status="active", vendor_key="super-secret-vendor-key",
        setup_url="https://smartticket-acme.onrender.com/setup?token=abc123", welcome_email_sent=True,
    )
    client = TestClient(fleet_admin.app)

    response = client.post("/instances/create", data={
        "client_name": "Acme Corp", "slug": "acme", "admin_email": "a@acme.com", "postgres_plan": "basic_256mb",
    })

    assert "super-secret-vendor-key" not in response.text


def test_index_shows_postgres_plan_dropdown_with_default_selected(monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    client = TestClient(fleet_admin.app)

    html = client.get("/").text

    assert 'value="basic_256mb" selected' in html
    for plan in fleet_admin.render.SUPPORTED_POSTGRES_PLANS:
        assert f'value="{plan}"' in html


def test_no_meta_refresh_when_no_job_running(monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    client = TestClient(fleet_admin.app)

    assert 'http-equiv="refresh"' not in client.get("/").text


def test_meta_refresh_present_while_a_job_is_running(monkeypatch):
    """Rafraîchissement automatique honnête : tant qu'un provisioning tourne, la page se
    recharge seule pour suivre la progression, sans qu'il faille du JS de polling dédié."""
    monkeypatch.setattr(render_client, "RENDER_API_KEY", None)
    fleet_admin._provision_jobs["acme"] = fleet_admin.ProvisionJob(
        slug="acme", client_name="Acme Corp", status="running", started_at=datetime.now(timezone.utc),
    )

    client = TestClient(fleet_admin.app)
    html = client.get("/").text

    assert 'http-equiv="refresh"' in html
    assert "en cours depuis" in html
