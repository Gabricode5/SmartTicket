import json
import os
import time
from typing import Generator

import requests


MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1").rstrip("/")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_EMBED_MODEL = os.getenv("EMBED_MODEL", "mistral-embed")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
MISTRAL_MAX_RETRIES = int(os.getenv("MISTRAL_MAX_RETRIES", "5"))
MISTRAL_BACKOFF_SECONDS = float(os.getenv("MISTRAL_BACKOFF_SECONDS", "2"))


def _require_api_key() -> str:
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY manquante. Définis-la dans l'environnement.")
    return MISTRAL_API_KEY


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_require_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _extract_text_content(message_content) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        parts: list[str] = []
        for item in message_content:
            if isinstance(item, dict):
                text_value = item.get("text")
                if text_value:
                    parts.append(str(text_value))
        return "".join(parts)
    return ""


def _request_with_retry(
    method: str,
    url: str,
    *,
    timeout,
    **kwargs,
) -> requests.Response:
    last_error: Exception | None = None

    for attempt in range(MISTRAL_MAX_RETRIES):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            if response.status_code == 429 and attempt < MISTRAL_MAX_RETRIES - 1:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else MISTRAL_BACKOFF_SECONDS * (attempt + 1)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            last_error = exc
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= MISTRAL_MAX_RETRIES - 1:
                raise
            time.sleep(MISTRAL_BACKOFF_SECONDS * (attempt + 1))

    if last_error:
        raise last_error
    raise RuntimeError("Requete Mistral invalide")


def generate_text(prompt: str, model: str | None = None, timeout: int = 30) -> str:
    payload = {
        "model": model or MISTRAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "text"},
    }
    response = _request_with_retry(
        "POST",
        f"{MISTRAL_API_URL}/chat/completions",
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise ValueError("Réponse Mistral invalide")
    message = choices[0].get("message", {})
    text = _extract_text_content(message.get("content"))
    if not text:
        raise ValueError("Réponse Mistral vide")
    return text


def stream_text(prompt: str, model: str | None = None, timeout: int = 30) -> Generator[str, None, None]:
    payload = {
        "model": model or MISTRAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "response_format": {"type": "text"},
    }
    response = _request_with_retry(
        "POST",
        f"{MISTRAL_API_URL}/chat/completions",
        headers={**_headers(), "Accept": "text/event-stream"},
        json=payload,
        stream=True,
        timeout=(timeout, None),
    )
    response.raise_for_status()

    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line or not raw_line.startswith("data:"):
            continue
        data_str = raw_line[5:].strip()
        if not data_str or data_str == "[DONE]":
            continue
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        choices = event.get("choices") if isinstance(event, dict) else None
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        token = _extract_text_content(delta.get("content"))
        if token:
            yield token


def embed_text(text: str, model: str | None = None, timeout: int = 30) -> list[float]:
    return embed_texts([text], model=model, timeout=timeout)[0]


def embed_texts(texts: list[str], model: str | None = None, timeout: int = 30) -> list[list[float]]:
    payload = {
        "model": model or MISTRAL_EMBED_MODEL,
        "input": texts,
    }
    response = _request_with_retry(
        "POST",
        f"{MISTRAL_API_URL}/embeddings",
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    rows = data.get("data") if isinstance(data, dict) else None
    if not rows:
        raise ValueError("Réponse embeddings Mistral invalide")

    embeddings: list[list[float]] = []
    for row in rows:
        vector = row.get("embedding") if isinstance(row, dict) else None
        if not vector:
            raise ValueError("Embedding Mistral manquant")
        embeddings.append(vector)
    return embeddings
