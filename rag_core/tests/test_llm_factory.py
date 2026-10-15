import pytest

from rag_core.llm.base import Embedder, Generator
from rag_core.llm.errors import UnknownModelError
from rag_core.llm.factory import get_embedder, get_generator
from rag_core.llm.gemini import GeminiProvider
from rag_core.llm.mistral import MistralProvider


def test_default_generator_is_mistral_small():
    gen = get_generator()
    assert isinstance(gen, Generator)
    assert gen.model == "mistral-small-latest"
    assert isinstance(gen.provider, MistralProvider)
    assert gen.provider.name == "mistral"


def test_default_embedder_is_mistral_embed_1024():
    emb = get_embedder()
    assert isinstance(emb, Embedder)
    assert emb.model == "mistral-embed"
    assert emb.dimension == 1024


def test_explicit_catalogue_model_is_accepted():
    gen = get_generator("mistral-large-latest")
    assert gen.model == "mistral-large-latest"


def test_offcatalogue_model_is_rejected_by_factory():
    with pytest.raises(UnknownModelError):
        get_generator("llama-local-7b")
    with pytest.raises(UnknownModelError):
        get_embedder("text-embedding-ada-002")


def test_provider_instances_are_reused():
    assert get_generator().provider is get_generator("mistral-large-latest").provider


def test_gemini_generator_resolves_to_gemini_provider():
    gen = get_generator("gemini-3.5-flash-lite")
    assert gen.model == "gemini-3.5-flash-lite"
    assert isinstance(gen.provider, GeminiProvider)
    assert gen.provider.name == "gemini"


def test_gemini_embedder_requires_matching_embedding_dimension(monkeypatch):
    from rag_core import config

    monkeypatch.setattr(config, "EMBEDDING_DIMENSION", 1536)
    emb = get_embedder("gemini-embedding-001")
    assert emb.model == "gemini-embedding-001"
    assert emb.dimension == 1536
    assert isinstance(emb.provider, GeminiProvider)


def test_claude_generator_resolves_to_claude_provider():
    from rag_core.llm.claude import ClaudeProvider

    gen = get_generator("claude-haiku-5-5")
    assert gen.model == "claude-haiku-5-5"
    assert isinstance(gen.provider, ClaudeProvider)
    assert gen.provider.name == "claude"


def test_openai_generator_and_embedder_resolve_to_openai_provider(monkeypatch):
    from rag_core import config
    from rag_core.llm.openai_compatible import OpenAIProvider

    gen = get_generator("gpt-6-luna")
    assert isinstance(gen.provider, OpenAIProvider)
    assert gen.provider.name == "openai"

    monkeypatch.setattr(config, "EMBEDDING_DIMENSION", 1536)
    emb = get_embedder("text-embedding-3-small")
    assert isinstance(emb.provider, OpenAIProvider)
    assert emb.dimension == 1536


def test_claude_provider_embed_raises_clear_error():
    from rag_core.llm.claude import ClaudeProvider

    with pytest.raises(RuntimeError, match="pas d'API d'embeddings"):
        ClaudeProvider(api_key="dummy").embed(["x"], model="claude-haiku-5-5", timeout=5)


def test_ollama_generator_and_embedder_resolve_to_ollama_provider(monkeypatch):
    from rag_core import config
    from rag_core.llm.openai_compatible import OllamaProvider

    gen = get_generator("llama3.1")
    assert isinstance(gen.provider, OllamaProvider)
    assert gen.provider.name == "ollama"

    monkeypatch.setattr(config, "EMBEDDING_DIMENSION", 768)
    emb = get_embedder("nomic-embed-text")
    assert isinstance(emb.provider, OllamaProvider)
    assert emb.dimension == 768
