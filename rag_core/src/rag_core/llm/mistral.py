"""Implementation LLMProvider pour l'API Mistral.

Portage de backend/mistral_client.py : meme logique de retry/backoff sur 429, memes
appels /chat/completions (non streame) et /embeddings. Le streaming SSE du backend n'est
pas repris -- rag_core produit une suggestion complete pour un agent, pas un flux token.
"""
import time

import requests

from rag_core.config import (
    MISTRAL_API_KEY,
    MISTRAL_API_URL,
    MISTRAL_BACKOFF_SECONDS,
    MISTRAL_MAX_RETRIES,
)
from rag_core.llm.base import LLMProvider


def _extract_text_content(message_content) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        parts: list[str] = []
        for item in message_content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts)
    return ""


class MistralProvider(LLMProvider):
    name = "mistral"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_url: str | None = None,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
    ):
        self._api_key = api_key if api_key is not None else MISTRAL_API_KEY
        self._api_url = (api_url or MISTRAL_API_URL).rstrip("/")
        self._max_retries = MISTRAL_MAX_RETRIES if max_retries is None else max_retries
        self._backoff = MISTRAL_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise RuntimeError("MISTRAL_API_KEY manquante. Definis-la dans l'environnement.")
        return self._api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._require_api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request_with_retry(self, method: str, url: str, *, timeout, **kwargs) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = requests.request(method, url, timeout=timeout, **kwargs)
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
        raise RuntimeError("Requete Mistral invalide")

    def generate(self, prompt: str, *, model: str, timeout: float) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "text"},
        }
        response = self._request_with_retry(
            "POST",
            f"{self._api_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=timeout,
        )
        data = response.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise ValueError("Reponse Mistral invalide")
        text = _extract_text_content(choices[0].get("message", {}).get("content"))
        if not text:
            raise ValueError("Reponse Mistral vide")
        return text

    def embed(self, texts: list[str], *, model: str, timeout: float) -> list[list[float]]:
        response = self._request_with_retry(
            "POST",
            f"{self._api_url}/embeddings",
            headers=self._headers(),
            json={"model": model, "input": texts},
            timeout=timeout,
        )
        data = response.json()
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            raise ValueError("Reponse embeddings Mistral invalide")
        vectors: list[list[float]] = []
        for row in rows:
            vector = row.get("embedding") if isinstance(row, dict) else None
            if not vector:
                raise ValueError("Embedding Mistral manquant")
            vectors.append(vector)
        return vectors
