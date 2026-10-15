"""Couche LLM abstraite de rag_core.

- base.py       : interface LLMProvider + wrappers lies Embedder / Generator
- catalogue.py  : CATALOGUE FERME des modeles autorises (nom -> fournisseur + type)
- mistral.py    : implementation MistralProvider (seule pour l'instant)
- factory.py    : resolution modele -> provider, point d'entree get_embedder / get_generator
- errors.py     : erreurs typees (modele inconnu, mauvais type, dimension incoherente...)

Ajouter un fournisseur (OpenAI, modele local...) = une nouvelle classe LLMProvider dans
un module dedie + une entree dans catalogue._CATALOGUE + une entree dans factory._PROVIDERS.
Aucune autre partie de rag_core ne change.
"""
from rag_core.llm.base import Embedder, Generator, LLMProvider
from rag_core.llm.catalogue import ModelKind, ModelSpec, catalogue, resolve
from rag_core.llm.factory import get_embedder, get_generator

__all__ = [
    "LLMProvider",
    "Embedder",
    "Generator",
    "ModelKind",
    "ModelSpec",
    "catalogue",
    "resolve",
    "get_embedder",
    "get_generator",
]
