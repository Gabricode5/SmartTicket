"""Bout-en-bout DRY_RUN=false : le VRAI GlpiClient écrit réellement un ITILFollowup
is_private via de vraies requêtes HTTP contre un serveur GLPI stub local.

Ceci vérifie le dernier maillon de notre côté (client -> HTTP -> écriture d'un suivi
privé). Le test contre une vraie image glpi/glpi vit dans tests/e2e/ (auto-skip sans
Docker/GLPI joignable) et valide en plus que GLPI accepte notre format de payload.

`DRY_RUN=false` est forcé LOCALEMENT dans ce fichier ; le défaut du projet reste True.
"""
import importlib

import requests

from glpi_connector import config as config_mod
from glpi_connector.glpi_client import GlpiClient
from glpi_connector.models import ProcessedTicket
from glpi_connector.poller import run_once
from tests._fakes import FakeAnswer
from tests._glpi_stub import GlpiStub


def test_real_client_writes_private_followup_over_http():
    stub = GlpiStub()
    stub.seed_ticket(101, "PC lent", "<p>Mon poste rame depuis la mise à jour.</p>", status=1)
    with stub:
        client = GlpiClient(stub.base_url, app_token="APP", user_token="USR", http=requests.Session())
        token = client.init_session()
        assert token in stub.sessions

        created = client.add_followup(
            101, "[Suggestion IA - à valider]\n\nRedémarrez le poste puis videz le cache.",
            is_private=True,
        )
        assert created["id"] == 1
        client.kill_session()

    assert stub.sessions == set()                       # killSession a bien retiré le token
    (fu,) = stub.followups
    assert fu["itemtype"] == "Ticket"
    assert fu["items_id"] == 101
    assert fu["is_private"] == 1                        # PRIVÉ écrit côté serveur
    assert fu["content"].startswith("[Suggestion IA - à valider]")


def test_poller_dry_run_false_end_to_end_over_http(db):
    stub = GlpiStub()
    stub.seed_ticket(201, "Imprimante HS", "<p>Voyant éteint, rien à l'écran.</p>", status=1)
    stub.seed_ticket(202, "Déjà pris en charge", "<p>en cours</p>", status=2)

    with stub:
        client = GlpiClient(stub.base_url, app_token="A", user_token="U", http=requests.Session())
        with client:
            stats = run_once(
                db, client,
                dry_run=False,                          # forcé ici, pas dans la config
                answer_fn=lambda q: FakeAnswer(f"Piste de résolution : {q[:30]}"),
                statuses=[1],
            )

    assert stats.answered == 1 and stats.errors == 0
    (fu,) = stub.followups                              # un seul suivi, pour le ticket 201
    assert fu["items_id"] == 201
    assert fu["is_private"] == 1
    assert fu["content"].startswith("[Suggestion IA - à valider]")
    assert "assistance d'une IA" in fu["content"]

    row = db.get(ProcessedTicket, 201)
    assert row.status == "answered"
    assert row.followup_id == fu["id"]
    assert db.get(ProcessedTicket, 202) is None         # statut != 1 -> jamais touché


def test_project_default_dry_run_is_still_true():
    reloaded = importlib.reload(config_mod)
    assert reloaded.DRY_RUN is True
