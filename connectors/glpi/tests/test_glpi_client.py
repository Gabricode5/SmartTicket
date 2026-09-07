"""glpi_client testé contre les fixtures JSON (aucune instance GLPI réelle)."""
import pytest

from glpi_connector.glpi_client import GlpiClient, GlpiError
from tests._fakes import FakeGlpiHttp


def _client(http=None):
    return GlpiClient(
        "https://glpi.test.local/apirest.php",
        app_token="APP",
        user_token="USR",
        http=http or FakeGlpiHttp(),
    )


def test_init_session_sets_and_returns_token():
    http = FakeGlpiHttp()
    c = _client(http)
    token = c.init_session()
    assert token == "sess-abc-123"
    # initSession : App-Token + Authorization user_token, PAS de Session-Token
    call = next(x for x in http.calls if x["url"].endswith("/initSession"))
    assert call["headers"]["App-Token"] == "APP"
    assert call["headers"]["Authorization"] == "user_token USR"


def test_request_before_session_raises():
    with pytest.raises(GlpiError):
        _client().get_ticket(12)


def test_get_ticket_returns_fixture():
    c = _client()
    c.init_session()
    ticket = c.get_ticket(12)
    assert ticket["id"] == 12
    assert ticket["status"] == 1
    assert "imprimante" in ticket["content"].lower()


def test_list_tickets_filters_by_status():
    c = _client()
    c.init_session()
    all_rows = c.list_tickets()
    assert {t["id"] for t in all_rows} == {12, 13, 14}
    new_only = c.list_tickets(statuses=[1])
    assert {t["id"] for t in new_only} == {12, 13}


def test_add_followup_posts_expected_payload():
    http = FakeGlpiHttp()
    c = _client(http)
    c.init_session()
    created = c.add_followup(12, "Texte de suggestion", is_private=True)

    assert created["id"] == 990
    post = next(x for x in http.calls if x["method"] == "POST")
    assert post["url"].endswith("/ITILFollowup")
    assert post["headers"]["Session-Token"] == "sess-abc-123"
    assert post["json"]["input"] == {
        "itemtype": "Ticket",
        "items_id": 12,
        "content": "Texte de suggestion",
        "is_private": 1,
    }


def test_add_followup_is_private_false_maps_to_zero():
    http = FakeGlpiHttp()
    c = _client(http)
    c.init_session()
    c.add_followup(12, "x", is_private=False)
    post = next(x for x in http.calls if x["method"] == "POST")
    assert post["json"]["input"]["is_private"] == 0


def test_kill_session_clears_token_and_calls_endpoint():
    http = FakeGlpiHttp()
    c = _client(http)
    c.init_session()
    c.kill_session()
    assert any(x["url"].endswith("/killSession") for x in http.calls)
    with pytest.raises(GlpiError):
        c.get_ticket(12)  # plus de session


def test_context_manager_opens_and_closes_session():
    http = FakeGlpiHttp()
    with GlpiClient("https://glpi.test.local/apirest.php", app_token="A", user_token="U", http=http) as c:
        assert c.get_ticket(12)["id"] == 12
    urls = [x["url"] for x in http.calls]
    assert any(u.endswith("/initSession") for u in urls)
    assert any(u.endswith("/killSession") for u in urls)
