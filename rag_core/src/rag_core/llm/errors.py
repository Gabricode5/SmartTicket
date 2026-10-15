"""Erreurs typees de la couche LLM."""


class LLMError(Exception):
    """Base de toutes les erreurs de la couche LLM."""


class UnknownModelError(LLMError):
    """Modele absent du catalogue ferme."""

    def __init__(self, name: str, allowed: list[str]):
        self.name = name
        self.allowed = allowed
        super().__init__(
            f"Modele '{name}' inconnu. Modeles autorises (catalogue ferme) : {', '.join(allowed)}"
        )


class ModelKindMismatch(LLMError):
    """Modele utilise pour un usage qui n'est pas le sien (ex: modele d'embedding demande
    pour de la generation)."""

    def __init__(self, name: str, actual: str, expected: str):
        self.name = name
        self.actual = actual
        self.expected = expected
        super().__init__(
            f"Modele '{name}' est de type '{actual}', or un modele '{expected}' est attendu ici."
        )


class UnknownProviderError(LLMError):
    """Le catalogue reference un fournisseur qui n'a pas d'implementation enregistree."""

    def __init__(self, name: str, allowed: list[str]):
        self.name = name
        self.allowed = allowed
        super().__init__(
            f"Fournisseur '{name}' sans implementation. Fournisseurs disponibles : {', '.join(allowed)}"
        )


class EmbeddingDimensionMismatch(LLMError):
    """La dimension du modele d'embedding du catalogue ne correspond pas a la colonne
    vectorielle configuree (EMBEDDING_DIMENSION)."""

    def __init__(self, model: str, model_dim: int | None, configured_dim: int):
        self.model = model
        self.model_dim = model_dim
        self.configured_dim = configured_dim
        super().__init__(
            f"Le modele d'embedding '{model}' produit des vecteurs de dimension {model_dim}, "
            f"mais EMBEDDING_DIMENSION={configured_dim}. Aligne la colonne pgvector et la config."
        )
