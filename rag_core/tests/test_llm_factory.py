import pytest

from rag_core.llm.base import Embedder, Generator
from rag_core.llm.errors import UnknownModelError
from rag_core.llm.factory import get_embedder, get_generator
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
        get_embedder("text-embedding-3-small")


def test_provider_instances_are_reused():
    assert get_generator().provider is get_generator("mistral-large-latest").provider
