"""Les defaults prudents sont bien en config (pas en dur ailleurs) et corrects."""
import importlib

import pytest

from glpi_connector import config


def test_prudent_defaults():
    assert config.DRY_RUN is True                       # dry-run par défaut
    assert config.RESPONSE_MODE == "suggested"          # seul mode autorisé
    assert config.GLPI_API_VERSION == "10"              # GLPI 10.x
    assert config.GLPI_FOLLOWUP_ITEMTYPE == "ITILFollowup"
    assert config.FOLLOWUP_IS_PRIVATE is True
    assert config.SUGGESTION_PREFIX == "[Suggestion IA - à valider]"
    assert config.GLPI_TICKET_STATUS_FILTER == [1]      # nouveaux uniquement


def test_dry_run_is_strict(monkeypatch):
    """Seule la valeur littérale "false" (casse indifférente) désarme le dry-run."""
    cases = [
        ("false", False), ("False", False), ("FALSE", False), (" false ", False),
        ("true", True), ("0", True), ("", True), ("no", True), ("oui", True),
    ]
    try:
        for value, expected in cases:
            monkeypatch.setenv("DRY_RUN", value)
            reloaded = importlib.reload(config)
            assert reloaded.DRY_RUN is expected, f"DRY_RUN={value!r}"
    finally:
        monkeypatch.delenv("DRY_RUN", raising=False)
        importlib.reload(config)


def test_response_mode_guard_rejects_non_suggested(monkeypatch):
    """Un mode autre que 'suggested' fait échouer le chargement de la config."""
    try:
        monkeypatch.setenv("RESPONSE_MODE", "auto")
        with pytest.raises(RuntimeError, match="RESPONSE_MODE"):
            importlib.reload(config)
    finally:
        monkeypatch.delenv("RESPONSE_MODE", raising=False)
        importlib.reload(config)
