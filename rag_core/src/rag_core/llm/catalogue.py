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


# Mistral par defaut (Q15). Ajouts futurs (OpenAI, modele local) : nouvelles entrees, meme
# forme. Garder cette liste courte et explicite -- c'est la surface de support assumee.
_CATALOGUE: dict[str, ModelSpec] = {
    "mistral-small-latest": ModelSpec("mistral-small-latest", "mistral", ModelKind.GENERATE),
    "mistral-large-latest": ModelSpec("mistral-large-latest", "mistral", ModelKind.GENERATE),
    "mistral-embed": ModelSpec("mistral-embed", "mistral", ModelKind.EMBED, dimension=1024),
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
