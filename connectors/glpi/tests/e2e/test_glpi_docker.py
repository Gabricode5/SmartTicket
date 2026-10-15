"""Bout-en-bout contre une VRAIE instance glpi/glpi (Docker).

Auto-skip si GLPI_E2E_URL n'est pas défini ou si l'instance est injoignable — ce test
n'est jamais un faux rouge en CI sans Docker. Voir tests/e2e/README.md pour la mise en
route (docker compose + assistant d'install + création des tokens).

Ce que ça vérifie EN PLUS du stub HTTP (tests/test_e2e_http.py) : que GLPI accepte notre
format de payload (route ITILFollowup, noms de champs, en-têtes d'auth) et enregistre bien
le suivi comme PRIVÉ.

DRY_RUN=false est le comportement testé ici, forcé dans ce fichier ; le défaut projet
reste True.
"""
import os
import uuid

import pytest
import requests

from glpi_connector.glpi_client import GlpiClient

_URL = os.getenv("GLPI_E2E_URL")
_APP = os.getenv("GLPI_E2E_APP_TOKEN")
_USER = os.getenv("GLPI_E2E_USER_TOKEN")

pytestmark = pytest.mark.skipif(
    not (_URL and _APP and _USER),
    reason="GLPI_E2E_URL / GLPI_E2E_APP_TOKEN / GLPI_E2E_USER_TOKEN non définis "
    "(cf. tests/e2e/README.md)",
)


@pytest.fixture
def glpi():
    try:
        requests.get(f"{_URL.rstrip('/')}/initSession", timeout=5)
    except requests.RequestException as exc:
        pytest.skip(f"GLPI injoignable sur {_URL}: {exc}")
    client = GlpiClient(_URL, app_token=_APP, user_token=_USER, http=requests.Session())
    client.init_session()
    yield client
    client.kill_session()


def _create_ticket(client: GlpiClient) -> int:
    marker = uuid.uuid4().hex[:8]
    result = client._request(
        "POST",
        "Ticket",
        json={"input": {"name": f"[e2e {marker}] imprimante HS",
                        "content": f"<p>Ticket e2e {marker} — voyant éteint.</p>"}},
    )
    if isinstance(result, list):
        result = result[0]
    return result["id"]


def test_client_writes_real_private_followup(glpi):
    ticket_id = int(os.getenv("GLPI_E2E_TICKET_ID") or _create_ticket(glpi))

    content = f"[Suggestion IA - à valider]\n\nRedémarrer le poste. (e2e {uuid.uuid4().hex[:6]})"
    created = glpi.add_followup(ticket_id, content, is_private=True)
    followup_id = created["id"]
    assert followup_id

    # Relecture côté GLPI : le suivi existe, rattaché au bon ticket, et il est PRIVÉ.
    stored = glpi._request("GET", f"ITILFollowup/{followup_id}")
    assert int(stored["items_id"]) == ticket_id
    assert stored["itemtype"] == "Ticket"
    assert int(stored["is_private"]) == 1
    assert stored["content"].startswith("[Suggestion IA - à valider]")
