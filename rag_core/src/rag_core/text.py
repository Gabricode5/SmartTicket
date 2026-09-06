"""Nettoyage et scoring qualite du texte a ingerer.

Portage VERBATIM de la logique de backend/ingest_postgres.py (_sanitize_text +
chunk_quality_score) : memes heuristiques (caracteres de remplacement U+FFFD, ratio de
'?', signatures binaires, blobs base64), memes seuils. Module PUR (stdlib uniquement),
testable sans base.
"""
import re

# Signatures typiques d'un binaire (image, PDF...) mal extrait en texte.
BINARY_SIGNATURE_PATTERNS = (
    "Exif",
    "xmp.did",
    "Adobe",
    "Photoshop",
    "JFIF",
    "ICC_PROFILE",
)

_CONTROL_RE = re.compile(r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]")
_WHITESPACE_RE = re.compile(r"\s+")
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/=]{120,}")


def clean_text(value: str) -> str:
    """Retire NUL + caracteres de controle, normalise les espaces."""
    sanitized = (value or "").replace("\x00", "")
    sanitized = _CONTROL_RE.sub(" ", sanitized)
    sanitized = _WHITESPACE_RE.sub(" ", sanitized)
    return sanitized.strip()


def quality_score(value: str) -> float:
    """Score de qualite entre 0.0 (corrompu) et 1.0 (propre)."""
    if not value:
        return 0.0

    score = 1.0

    weird_chars = sum(
        1 for c in value if ord(c) == 65533 or (not c.isprintable() and not c.isspace())
    )
    score -= (weird_chars / max(len(value), 1)) * 2

    score -= (value.count("?") / max(len(value), 1)) * 5

    lowered = value.lower()
    if any(sig.lower() in lowered for sig in BINARY_SIGNATURE_PATTERNS):
        score -= 0.5

    if _BASE64_BLOB_RE.search(value):
        score -= 0.5

    return max(0.0, min(1.0, score))
