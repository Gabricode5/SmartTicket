"""Implementation LLMProvider pour l'API Gemini (Google).

Alternative a Mistral (cf. mistral.py) -- meme contrat LLMProvider. Format de requete/
reponse propre a Gemini : auth par header `x-goog-api-key` (pas de Bearer token), modele
nomme `models/{model}` dans le corps, texte imbrique dans `content.parts[].text`.

Verifie en direct (pas seulement sur la doc) le 2026-10-14 :
  - generateContent : POST /v1beta/models/{model}:generateContent -> candidates[0].content.parts[].text
  - embedContent     : POST /v1beta/models/{model}:embedContent    -> embedding.values (singulier)
  - batchEmbedContents : POST /v1beta/models/{model}:batchEmbedContents, un `output_dimensionality`
    par item de `requests[]`, respecte -> embeddings[].values (pluriel), meme ordre que l'entree.
"""
import time

import requests

from rag_core.config import (
    GEMINI_API_KEY,
    GEMINI_API_URL,
    GEMINI_BACKOFF_SECONDS,
    GEMINI_MAX_RETRIES,
)
from rag_core.llm.base import LLMProvider
from rag_core.llm.catalogue import ModelKind, resolve


def _extract_text(candidates) -> str:
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text"))


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_url: str | None = None,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
    ):
        self._api_key = api_key if api_key is not None else GEMINI_API_KEY
        self._api_url = (api_url or GEMINI_API_URL).rstrip("/")
        self._max_retries = GEMINI_MAX_RETRIES if max_retries is None else max_retries
        self._backoff = GEMINI_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY manquante. Definis-la dans l'environnement.")
        return self._api_key

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-goog-api-key": self._require_api_key()}

    def _post_with_retry(self, url: str, payload: dict, *, timeout: float) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = requests.post(url, headers=self._headers(), json=payload, timeout=timeout)
                if response.status_code == 429 and attempt < self._max_retries - 1:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else self._backoff * (attempt + 1)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                last_error = exc
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self._max_retries - 1:
                    raise
                time.sleep(self._backoff * (attempt + 1))
        if last_error:
            raise last_error
        raise RuntimeError("Requete Gemini invalide")

    def generate(self, prompt: str, *, model: str, timeout: float) -> str:
        url = f"{self._api_url}/models/{model}:generateContent"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = self._post_with_retry(url, payload, timeout=timeout)
        data = response.json()
        text = _extract_text(data.get("candidates"))
        if not text:
            raise ValueError("Reponse Gemini vide")
        return text

    def embed(self, texts: list[str], *, model: str, timeout: float) -> list[list[float]]:
        """Un seul appel batchEmbedContents pour toute la liste (meme principe que l'embed
        par batch de rag_core.ingest -- une requete HTTP, pas une par texte)."""
        url = f"{self._api_url}/models/{model}:batchEmbedContents"
        dimension = resolve(model, expected_kind=ModelKind.EMBED).dimension
        payload = {
            "requests": [
                {
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": text}]},
                    "output_dimensionality": dimension,
                }
                for text in texts
            ]
        }
        response = self._post_with_retry(url, payload, timeout=timeout)
        data = response.json()
        rows = data.get("embeddings")
        if not rows:
            raise ValueError("Reponse embeddings Gemini invalide")
        vectors: list[list[float]] = []
        for row in rows:
            values = row.get("values") if isinstance(row, dict) else None
            if not values:
                raise ValueError("Embedding Gemini manquant")
            vectors.append(values)
        return vectors
