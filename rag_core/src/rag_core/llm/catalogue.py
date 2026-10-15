"""Catalogue FERME des modeles LLM autorises.

rag_core ne sait parler qu'aux modeles listes ici. Il n'existe volontairement aucun
mecanisme "passe n'importe quel nom de modele au fournisseur" : un modele non catalogue
leve UnknownModelError. Elargir le support = ajouter une entree ici (et, si c'est un
nouveau fournisseur, une implementation LLMProvider + une entree dans factory._PROVIDERS).

Module PUR : n'importe rien d'autre que la stdlib. Importable sans base ni cle API.
"""
from dataclasses import dataclass
from enum import Enum

from rag_core.llm.errors import ModelKindMismatch, UnknownModelError


class ModelKind(str, Enum):
    GENERATE = "generate"
    EMBED = "embed"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: str
    kind: ModelKind
    dimension: int | None = None  # renseigne uniquement pour kind == EMBED


# Mistral par defaut (Q15). Ajouts futurs (Claude, OpenAI, local) : nouvelles entrees, meme
# forme. Garder cette liste courte et explicite -- c'est la surface de support assumee.
_CATALOGUE: dict[str, ModelSpec] = {
    "mistral-small-latest": ModelSpec("mistral-small-latest", "mistral", ModelKind.GENERATE),
    "mistral-large-latest": ModelSpec("mistral-large-latest", "mistral", ModelKind.GENERATE),
    "mistral-embed": ModelSpec("mistral-embed", "mistral", ModelKind.EMBED, dimension=1024),
    # Gemini (Google) -- verifie en direct le 2026-10-14 : gemini-2.5-flash est deconseille
    # pour un nouveau projet (acces restreint aux comptes l'ayant deja utilise), Google
    # recommande gemini-3.5-flash-lite / gemini-3.8-flash pour tout nouveau projet.
    # gemini-embedding-001 a une dimension configurable (output_dimensionality) ; 1536 est
    # une des valeurs recommandees par la doc (768/1536/3072).
    "gemini-3.5-flash-lite": ModelSpec("gemini-3.5-flash-lite", "gemini", ModelKind.GENERATE),
    "gemini-embedding-001": ModelSpec(
        "gemini-embedding-001", "gemini", ModelKind.EMBED, dimension=1536
    ),
    # Claude (Anthropic) -- verifie le 2026-10-15 sur platform.claude.com. Generation
    # uniquement : Anthropic n'a pas d'API d'embeddings (ClaudeProvider.embed() leve).
    "claude-haiku-5-5": ModelSpec("claude-haiku-5-5", "claude", ModelKind.GENERATE),
    # OpenAI -- verifie le 2026-10-15 sur developers.openai.com. gpt-6-luna = palier
    # economique/haut-volume, coherent avec les defauts "small"/"flash-lite" des autres
    # fournisseurs. text-embedding-3-small : 1536 dimensions, stable depuis des annees.
    "gpt-6-luna": ModelSpec("gpt-6-luna", "openai", ModelKind.GENERATE),
    "text-embedding-3-small": ModelSpec(
        "text-embedding-3-small", "openai", ModelKind.EMBED, dimension=1536
    ),
    # Local (Ollama par defaut, cf. rag_core.llm.openai_compatible.OllamaProvider). Les
    # noms ci-dessous supposent `ollama pull llama3.1` / `ollama pull nomic-embed-text`
    # fait au prealable -- un autre modele local = une autre entree ici, meme forme.
    "llama3.1": ModelSpec("llama3.1", "ollama", ModelKind.GENERATE),
    "nomic-embed-text": ModelSpec("nomic-embed-text", "ollama", ModelKind.EMBED, dimension=768),
}

DEFAULT_GENERATION_MODEL = "mistral-small-latest"
DEFAULT_EMBEDDING_MODEL = "mistral-embed"


def resolve(model_name: str, *, expected_kind: ModelKind) -> ModelSpec:
    """Retourne la spec d'un modele catalogue, ou leve.

    UnknownModelError si le nom n'est pas au catalogue.
    ModelKindMismatch si le modele existe mais pour un autre usage.
    """
    spec = _CATALOGUE.get(model_name)
    if spec is None:
        raise UnknownModelError(model_name, sorted(_CATALOGUE))
    if spec.kind is not expected_kind:
        raise ModelKindMismatch(model_name, spec.kind.value, expected_kind.value)
    return spec


def catalogue() -> list[ModelSpec]:
    """Copie de la liste des modeles autorises (pour affichage / introspection)."""
    return list(_CATALOGUE.values())
