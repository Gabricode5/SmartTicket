"""Doublures LLM pour les tests : aucune requete reseau.

Elles respectent le contrat duck-type attendu par retriever/pipeline
(`.embed`, `.embed_one`, `.model`, `.dimension` / `.generate`).
"""
from rag_core.config import EMBEDDING_DIMENSION


def unit_vector(index: int) -> list[float]:
    """Vecteur one-hot de dimension EMBEDDING_DIMENSION (utile pour piloter la similarite)."""
    v = [0.0] * EMBEDDING_DIMENSION
    v[index % EMBEDDING_DIMENSION] = 1.0
    return v


class FakeEmbedder:
    model = "fake-embed"
    dimension = EMBEDDING_DIMENSION

    def __init__(self, mapping: dict[str, list[float]] | None = None):
        self._mapping = mapping or {}

    def _one(self, text: str) -> list[float]:
        if text in self._mapping:
            return self._mapping[text]
        return unit_vector(abs(hash(text)))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def embed_one(self, text: str) -> list[float]:
        return self._one(text)


class FakeGenerator:
    model = "fake-generate"

    def __init__(self, fn=None):
        self._fn = fn or (lambda prompt: "SUGGESTION")
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._fn(prompt)
