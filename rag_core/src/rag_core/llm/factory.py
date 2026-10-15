"""Point d'entree de la couche LLM : resout un nom de modele (via le catalogue ferme) en
un Embedder / Generator pret a l'emploi.

    get_generator()            -> Generator sur RAG_GENERATION_MODEL (defaut catalogue)
    get_generator("mistral-large-latest")
    get_embedder()             -> Embedder sur RAG_EMBEDDING_MODEL

Un nom hors catalogue leve UnknownModelError ; un modele du mauvais type leve
ModelKindMismatch ; un fournisseur catalogue sans implementation leve UnknownProviderError.
"""
from functools import lru_cache

from rag_core import config
from rag_core.llm.base import Embedder, Generator, LLMProvider
from rag_core.llm.catalogue import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_GENERATION_MODEL,
    ModelKind,
    resolve,
)
from rag_core.llm.claude import ClaudeProvider
from rag_core.llm.errors import EmbeddingDimensionMismatch, UnknownProviderError
from rag_core.llm.gemini import GeminiProvider
from rag_core.llm.mistral import MistralProvider
from rag_core.llm.openai_compatible import OllamaProvider, OpenAIProvider

# Fournisseur -> implementation. Ajouter un fournisseur de plus = une ligne ici + une
# entree catalogue (ou juste une entree catalogue si le fournisseur existe deja, ex: un
# autre modele Ollama).
_PROVIDERS: dict[str, type[LLMProvider]] = {
    "mistral": MistralProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


@lru_cache(maxsize=None)
def _provider(name: str) -> LLMProvider:
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        raise UnknownProviderError(name, sorted(_PROVIDERS)) from None
    return provider_cls()


def get_generator(model: str | None = None, *, timeout: float | None = None) -> Generator:
    chosen = model or config.GENERATION_MODEL or DEFAULT_GENERATION_MODEL
    spec = resolve(chosen, expected_kind=ModelKind.GENERATE)
    return Generator(
        provider=_provider(spec.provider),
        model=spec.name,
        timeout=config.REQUEST_TIMEOUT if timeout is None else timeout,
    )


def get_embedder(model: str | None = None, *, timeout: float | None = None) -> Embedder:
    chosen = model or config.EMBEDDING_MODEL or DEFAULT_EMBEDDING_MODEL
    spec = resolve(chosen, expected_kind=ModelKind.EMBED)
    if spec.dimension != config.EMBEDDING_DIMENSION:
        raise EmbeddingDimensionMismatch(spec.name, spec.dimension, config.EMBEDDING_DIMENSION)
    return Embedder(
        provider=_provider(spec.provider),
        model=spec.name,
        dimension=spec.dimension,
        timeout=config.REQUEST_TIMEOUT if timeout is None else timeout,
    )
