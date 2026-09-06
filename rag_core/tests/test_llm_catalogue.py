import pytest

from rag_core.llm.catalogue import ModelKind, catalogue, resolve
from rag_core.llm.errors import ModelKindMismatch, UnknownModelError


def test_resolve_known_generation_model():
    spec = resolve("mistral-small-latest", expected_kind=ModelKind.GENERATE)
    assert spec.provider == "mistral"
    assert spec.kind is ModelKind.GENERATE


def test_resolve_known_embedding_model_has_dimension():
    spec = resolve("mistral-embed", expected_kind=ModelKind.EMBED)
    assert spec.provider == "mistral"
    assert spec.dimension == 1024


def test_unknown_model_is_rejected():
    with pytest.raises(UnknownModelError) as exc:
        resolve("gpt-4o", expected_kind=ModelKind.GENERATE)
    assert "gpt-4o" in str(exc.value)
    # le message liste les modeles autorises
    assert "mistral-small-latest" in str(exc.value)


def test_model_used_for_wrong_purpose_is_rejected():
    with pytest.raises(ModelKindMismatch):
        resolve("mistral-embed", expected_kind=ModelKind.GENERATE)
    with pytest.raises(ModelKindMismatch):
        resolve("mistral-small-latest", expected_kind=ModelKind.EMBED)


def test_catalogue_is_closed_and_explicit():
    names = {spec.name for spec in catalogue()}
    assert names == {"mistral-small-latest", "mistral-large-latest", "mistral-embed"}
