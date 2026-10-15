"""Implementation LLMProvider pour l'API Anthropic (Claude) -- Messages API.

Generation uniquement : Anthropic n'expose aucune API d'embeddings (contrairement a
Mistral/Gemini/OpenAI). `embed()` existe pour satisfaire le contrat LLMProvider mais leve
toujours -- utiliser un autre fournisseur pour RAG_EMBEDDING_MODEL si RAG_GENERATION_MODEL
pointe vers Claude.

Format verifie sur la documentation officielle (platform.claude.com) le 2026-10-15,
non teste en direct (pas de cle API Anthropic disponible pendant le developpement) :
  POST {ANTHROPIC_API_URL}/messages
  headers: x-api-key, anthropic-version, content-type
  body: {"model", "max_tokens", "messages": [{"role": "user", "content": prompt}]}
  reponse: {"content": [{"type": "text", "text": "..."}], ...}
"""
import time

import requests

from rag_core.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_API_URL,
    ANTHROPIC_BACKOFF_SECONDS,
    ANTHROPIC_MAX_RETRIES,
    ANTHROPIC_VERSION,
)
from rag_core.llm.base import LLMProvider

# Reponse non streamee : suffisant pour une suggestion complete relue par un agent humain
# (meme choix que Mistral/Gemini), pas de raison de laisser le modele deborder longuement.
_DEFAULT_MAX_TOKENS = 2048


def _extract_text(content_blocks) -> str:
    if not content_blocks:
        return ""
    return "".join(
        block.get("text", "")
        for block in content_blocks
        if isinstance(block, dict) and block.get("type") == "text"
    )


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_url: str | None = None,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
    ):
        self._api_key = api_key if api_key is not None else ANTHROPIC_API_KEY
        self._api_url = (api_url or ANTHROPIC_API_URL).rstrip("/")
        self._max_retries = ANTHROPIC_MAX_RETRIES if max_retries is None else max_retries
        self._backoff = ANTHROPIC_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY manquante. Definis-la dans l'environnement.")
        return self._api_key

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._require_api_key(),
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

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
        raise RuntimeError("Requete Claude invalide")

    def generate(self, prompt: str, *, model: str, timeout: float) -> str:
        url = f"{self._api_url}/messages"
        payload = {
            "model": model,
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = self._post_with_retry(url, payload, timeout=timeout)
        data = response.json()
        text = _extract_text(data.get("content"))
        if not text:
            raise ValueError("Reponse Claude vide")
        return text

    def embed(self, texts: list[str], *, model: str, timeout: float) -> list[list[float]]:
        raise RuntimeError(
            "Anthropic (Claude) n'expose pas d'API d'embeddings. "
            "Choisis un autre fournisseur pour RAG_EMBEDDING_MODEL (gemini-embedding-001, "
            "mistral-embed, text-embedding-3-small...)."
        )
