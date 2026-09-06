"""Interface LLMProvider + wrappers lies (Embedder / Generator).

Un LLMProvider = un FOURNISSEUR (Mistral, OpenAI, modele local...), pas un modele.
Il expose deux capacites bas niveau, sans etat metier :

    embed(texts, *, model, timeout)    -> list[list[float]]
    generate(prompt, *, model, timeout) -> str

Le choix du modele concret et sa validation passent par le catalogue ferme
(rag_core.llm.catalogue) via la factory (rag_core.llm.factory) : un provider ne recoit
jamais un nom de modele arbitraire, seulement un nom deja resolu contre le catalogue.

Embedder / Generator sont de fines enveloppes IMMUABLES qui figent (provider, model,
timeout) pour que le reste de rag_core (retriever, pipeline) appelle `.embed_one(text)` /
`.generate(prompt)` sans se soucier du fournisseur.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMProvider(ABC):
    """Contrat commun a tous les fournisseurs LLM."""

    #: identifiant stable du fournisseur, doit correspondre a ModelSpec.provider
    name: str = ""

    @abstractmethod
    def embed(self, texts: list[str], *, model: str, timeout: float) -> list[list[float]]:
        """Vectorise une liste de textes. Retourne un vecteur par texte, dans l'ordre."""

    @abstractmethod
    def generate(self, prompt: str, *, model: str, timeout: float) -> str:
        """Genere une reponse texte a partir d'un prompt complet (non streame)."""


@dataclass(frozen=True)
class Embedder:
    """Vectoriseur lie a un modele d'embedding precis du catalogue."""

    provider: LLMProvider
    model: str
    dimension: int
    timeout: float

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.provider.embed(texts, model=self.model, timeout=self.timeout)
        for v in vectors:
            if len(v) != self.dimension:
                raise ValueError(
                    f"Le modele '{self.model}' a renvoye un vecteur de dimension {len(v)}, "
                    f"attendu {self.dimension}."
                )
        return vectors

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


@dataclass(frozen=True)
class Generator:
    """Generateur lie a un modele de generation precis du catalogue."""

    provider: LLMProvider
    model: str
    timeout: float

    def generate(self, prompt: str) -> str:
        return self.provider.generate(prompt, model=self.model, timeout=self.timeout)
