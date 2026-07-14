"""Tests de la forme exacte des requêtes/réponses render_client.py <-> l'API Render réelle.

Contrairement à ops/tests/test_provision_rollback.py (qui mocke render_client en bloc pour
tester l'orchestration de provision()), ces tests mockent uniquement `requests.request` — le
point d'entrée HTTP le plus bas possible — pour vérifier la forme EXACTE des payloads envoyés
et la façon dont les réponses sont déballées. C'est le niveau qui aurait détecté, avant le
premier run réel du 2026-07-14, que `version` manquait sur POST /postgres, que
`serviceDetails.env` est déprécié (il fallait `runtime`), que le Dockerfile devait aller sous
`envSpecificDetails` et pas `dockerDetails`, et que POST /services / GET .../deploys renvoient
des réponses enveloppées (`{"service": ...}` / `[{"deploy": ...}]`) et non les objets
directement. Vérifié contre le schéma OpenAPI réel de Render
(https://api-docs.render.com/v1.0/openapi/render-public-api-1.json), pas deviné.
"""
from unittest import mock

import pytest

import render_client


@pytest.fixture
def requests_mock():
    with mock.patch.object(render_client, "requests") as requests_mock:
        yield requests_mock


def _mock_response(requests_mock, *, status_code=201, json_body=None):
    response = mock.Mock()
    response.ok = 200 <= status_code < 300
    response.status_code = status_code
    response.content = b"{}"
    response.json.return_value = json_body or {}
    response.text = ""
    requests_mock.request.return_value = response
    return response


def _response(*, status_code=200, json_body=None, text=""):
    """Comme _mock_response() mais retourne l'objet SANS le poser sur requests_mock — pour
    construire une SÉQUENCE de réponses différentes (polling) via side_effect, plutôt qu'une
    seule réponse fixe via return_value."""
    response = mock.Mock()
    response.ok = 200 <= status_code < 300
    response.status_code = status_code
    response.content = b"{}" if json_body is not None or status_code >= 300 else b""
    response.json.return_value = json_body or {}
    response.text = text
    return response


def test_create_postgres_sends_required_version_field(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    _mock_response(requests_mock, json_body={"id": "pg-1"})

    render_client.create_postgres(
        name="db", owner_id="owner-1", plan="starter",
        database_name="db", database_user="admin", version="18",
    )

    _, kwargs = requests_mock.request.call_args
    assert kwargs["json"]["version"] == "18"


def test_create_postgres_rejects_unsupported_version_before_any_request(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")

    with pytest.raises(render_client.RenderAPIError, match="non supportée"):
        render_client.create_postgres(
            name="db", owner_id="owner-1", plan="starter",
            database_name="db", database_user="admin", version="9",
        )

    requests_mock.request.assert_not_called()


def test_create_web_service_uses_runtime_not_deprecated_env_field(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    _mock_response(requests_mock, json_body={
        "service": {"id": "svc-1", "serviceDetails": {"url": "https://svc-1.onrender.com"}},
        "deployId": "dep-1",
    })

    render_client.create_web_service(
        name="backend", owner_id="owner-1", repo="https://github.com/x/y", branch="main",
        root_dir="backend", dockerfile_path="./Dockerfile", env_vars={"A": "1"}, plan="starter",
    )

    _, kwargs = requests_mock.request.call_args
    service_details = kwargs["json"]["serviceDetails"]
    assert service_details["runtime"] == "docker"
    assert "env" not in service_details, "champ déprécié — ne doit plus être envoyé"
    assert service_details["envSpecificDetails"] == {"dockerfilePath": "./Dockerfile"}
    assert "dockerDetails" not in service_details, "mauvais niveau d'imbrication — remplacé par envSpecificDetails"


def test_create_web_service_unwraps_the_service_envelope(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    _mock_response(requests_mock, json_body={
        "service": {"id": "svc-1", "serviceDetails": {"url": "https://svc-1.onrender.com"}},
        "deployId": "dep-1",
    })

    result = render_client.create_web_service(
        name="backend", owner_id="owner-1", repo="https://github.com/x/y", branch="main",
        root_dir="backend", dockerfile_path="./Dockerfile", env_vars={}, plan="starter",
    )

    # POST /services renvoie {"service": {...}, "deployId": "..."} — sans déballage,
    # result["id"] lèverait un KeyError (la clé "id" n'existe qu'à l'intérieur de "service").
    assert result == {"id": "svc-1", "serviceDetails": {"url": "https://svc-1.onrender.com"}}


def test_get_latest_deploy_unwraps_the_deploy_envelope(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    _mock_response(requests_mock, json_body=[
        {"cursor": "abc", "deploy": {"id": "dep-1", "status": "live"}},
    ])

    result = render_client.get_latest_deploy("svc-1")

    # GET .../deploys renvoie [{"cursor": ..., "deploy": {...}}] — sans déballage,
    # result["status"] serait toujours absent (KeyError/None), et wait_for_deploy_live()
    # attendrait le timeout complet même sur un déploiement réussi.
    assert result == {"id": "dep-1", "status": "live"}


def test_get_latest_deploy_returns_none_when_no_deploys(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    _mock_response(requests_mock, json_body=[])

    assert render_client.get_latest_deploy("svc-1") is None


def test_wait_for_deploy_live_treats_pre_deploy_failed_as_terminal(monkeypatch):
    monkeypatch.setattr(
        render_client, "get_latest_deploy",
        lambda service_id: {"status": "pre_deploy_failed"},
    )

    with pytest.raises(render_client.RenderAPIError, match="pre_deploy_failed"):
        render_client.wait_for_deploy_live("svc-1", timeout_seconds=5, poll_interval_seconds=0)


def test_wait_for_deploy_live_returns_true_on_live_status(monkeypatch):
    monkeypatch.setattr(
        render_client, "get_latest_deploy",
        lambda service_id: {"status": "live"},
    )

    assert render_client.wait_for_deploy_live("svc-1", timeout_seconds=5, poll_interval_seconds=0) is True


# --- Race condition trouvée le 2026-07-15 : GET .../connection-info répond 404 juste après
# la création d'une base Postgres, car son statut est encore 'creating' — cf. render_client.py
# pour le détail. wait_for_postgres_available() doit polling GET /postgres/{id} (pas
# connection-info) jusqu'à 'available' avant que provision_client.py n'appelle
# get_postgres_connection_info().

def test_wait_for_postgres_available_polls_until_status_available(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    monkeypatch.setattr(render_client.time, "sleep", lambda _seconds: None)
    requests_mock.request.side_effect = [
        _response(json_body={"id": "pg-1", "status": "creating"}),
        _response(json_body={"id": "pg-1", "status": "creating"}),
        _response(json_body={"id": "pg-1", "status": "available"}),
    ]

    result = render_client.wait_for_postgres_available("pg-1", timeout_seconds=5, poll_interval_seconds=0)

    assert result is True
    assert requests_mock.request.call_count == 3


def test_wait_for_postgres_available_raises_on_recovery_failed(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    _mock_response(requests_mock, json_body={"id": "pg-1", "status": "recovery_failed"})

    with pytest.raises(render_client.RenderAPIError, match="recovery_failed"):
        render_client.wait_for_postgres_available("pg-1", timeout_seconds=5, poll_interval_seconds=0)


def test_wait_for_postgres_available_returns_false_on_timeout(requests_mock, monkeypatch):
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    monkeypatch.setattr(render_client.time, "sleep", lambda _seconds: None)
    # Reste bloquée en 'creating' indéfiniment dans ce test — jamais 'available'.
    _mock_response(requests_mock, json_body={"id": "pg-1", "status": "creating"})

    result = render_client.wait_for_postgres_available("pg-1", timeout_seconds=0, poll_interval_seconds=0)

    assert result is False


def test_get_latest_deploy_treats_404_as_not_ready_yet_rather_than_raising(requests_mock, monkeypatch):
    """Même classe de race condition que sur Postgres, pas reproduite en pratique à ce jour
    mais rien dans le schéma OpenAPI ne garantit qu'elle ne le sera jamais (cf. commentaire
    dans get_latest_deploy()) : un 404 juste après la création d'un service ne doit pas
    faire planter wait_for_deploy_live(), seulement le faire continuer à polling."""
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")

    not_found = _response(status_code=404, text='{"message":"not found"}')
    requests_mock.request.return_value = not_found

    assert render_client.get_latest_deploy("svc-1") is None


def test_wait_for_deploy_live_survives_a_transient_404_then_succeeds(requests_mock, monkeypatch):
    """Le scénario bout en bout demandé : la ressource n'est pas encore prête (404), puis
    elle l'est (deploy 'live') — wait_for_deploy_live() doit attendre plutôt qu'échouer."""
    monkeypatch.setattr(render_client, "RENDER_API_KEY", "test-key")
    monkeypatch.setattr(render_client.time, "sleep", lambda _seconds: None)
    requests_mock.request.side_effect = [
        _response(status_code=404, text='{"message":"not found"}'),
        _response(json_body=[{"cursor": "a", "deploy": {"id": "dep-1", "status": "build_in_progress"}}]),
        _response(json_body=[{"cursor": "b", "deploy": {"id": "dep-1", "status": "live"}}]),
    ]

    result = render_client.wait_for_deploy_live("svc-1", timeout_seconds=5, poll_interval_seconds=0)

    assert result is True
    assert requests_mock.request.call_count == 3
