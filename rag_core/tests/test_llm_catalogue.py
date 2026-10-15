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
    assert names == {
        "mistral-small-latest",
        "mistral-large-latest",
        "mistral-embed",
        "gemini-3.5-flash-lite",
        "gemini-embedding-001",
        "claude-haiku-5-5",
        "gpt-6-luna",
        "text-embedding-3-small",
        "llama3.1",
        "nomic-embed-text",
    }


def test_resolve_gemini_generation_model():
    spec = resolve("gemini-3.5-flash-lite", expected_kind=ModelKind.GENERATE)
    assert spec.provider == "gemini"
    assert spec.kind is ModelKind.GENERATE


def test_resolve_gemini_embedding_model_has_dimension():
    spec = resolve("gemini-embedding-001", expected_kind=ModelKind.EMBED)
    assert spec.provider == "gemini"
    assert spec.dimension == 1536


def test_resolve_claude_generation_model():
    spec = resolve("claude-haiku-5-5", expected_kind=ModelKind.GENERATE)
    assert spec.provider == "claude"
    assert spec.dimension is None


def test_claude_has_no_embedding_model():
    # Le modele existe (generation), mais pas en tant qu'embedding -- Anthropic n'a pas
    # d'API d'embeddings, aucune entree EMBED pour "claude" n'existe dans le catalogue.
    with pytest.raises(ModelKindMismatch):
        resolve("claude-haiku-5-5", expected_kind=ModelKind.EMBED)


def test_resolve_openai_models():
    gen = resolve("gpt-6-luna", expected_kind=ModelKind.GENERATE)
    assert gen.provider == "openai"
    emb = resolve("text-embedding-3-small", expected_kind=ModelKind.EMBED)
    assert emb.provider == "openai"
    assert emb.dimension == 1536


def test_resolve_ollama_models():
    gen = resolve("llama3.1", expected_kind=ModelKind.GENERATE)
    assert gen.provider == "ollama"
    emb = resolve("nomic-embed-text", expected_kind=ModelKind.EMBED)
    assert emb.provider == "ollama"
    assert emb.dimension == 768
