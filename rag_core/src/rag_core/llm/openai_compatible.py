"""Implementation LLMProvider pour toute API compatible OpenAI (/v1/chat/completions +
/v1/embeddings) : OpenAI lui-meme, Ollama, vLLM, LM Studio... meme format de requete/
reponse partout -- seuls l'URL de base et la necessite d'une vraie cle API changent.

Une seule classe, instanciee avec des defauts differents selon le fournisseur enregistre
dans factory._PROVIDERS ("openai" -> api.openai.com + cle obligatoire, "ollama" ->
localhost:11434/v1 + cle factice ignoree par le serveur). Pour viser un autre serveur
local (vLLM, LM Studio...), pas besoin d'une nouvelle classe : changer OLLAMA_API_URL (ou
ajouter une nouvelle entree de config + catalogue si le besoin est d'avoir les deux en
meme temps) suffit.

Format verifie sur la documentation officielle OpenAI (etabli, stable depuis des annees) ;
confirme pour Ollama via sa doc de compatibilite OpenAI. Non teste en direct ici (pas de
cle OpenAI disponible, serveur Ollama local present sur la machine mais pas demarre
pendant le developpement) :
  POST {api_url}/chat/completions -> {"choices": [{"message": {"content": "..."}}]}
  POST {api_url}/embeddings       -> {"data": [{"embedding": [...]}, ...]} (meme ordre que l'entree)
"""
import time

import requests

from rag_core.config import (
    OLLAMA_API_KEY,
    OLLAMA_API_URL,
    OLLAMA_BACKOFF_SECONDS,
    OLLAMA_MAX_RETRIES,
    OPENAI_API_KEY,
    OPENAI_API_URL,
    OPENAI_BACKOFF_SECONDS,
    OPENAI_MAX_RETRIES,
)
from rag_core.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """`name` est fixe par la sous-classe concrete (cf. OpenAIProvider / OllamaProvider) --
    c'est lui que la factory utilise pour choisir QUELLE config (cle/URL/retries) lire."""

    name = ""

    def __init__(
        self,
        *,
        api_key: str | None,
        api_url: str,
        max_retries: int,
        backoff_seconds: float,
        require_api_key: bool = True,
    ):
        self._api_key = api_key
        self._api_url = api_url.rstrip("/")
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._require_api_key = require_api_key

    def _require_key(self) -> str:
        if self._require_api_key and not self._api_key:
            raise RuntimeError(
                f"Cle API manquante pour le fournisseur '{self.name}'. "
                "Definis-la dans l'environnement."
            )
        return self._api_key or ""

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._require_key()}", "Content-Type": "application/json"}

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
        raise RuntimeError(f"Requete {self.name} invalide")

    def generate(self, prompt: str, *, model: str, timeout: float) -> str:
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        response = self._post_with_retry(f"{self._api_url}/chat/completions", payload, timeout=timeout)
        data = response.json()
        choices = data.get("choices")
        if not choices:
            raise ValueError(f"Reponse {self.name} invalide")
        text = (choices[0].get("message") or {}).get("content") or ""
        if not text:
            raise ValueError(f"Reponse {self.name} vide")
        return text

    def embed(self, texts: list[str], *, model: str, timeout: float) -> list[list[float]]:
        payload = {"model": model, "input": texts}
        response = self._post_with_retry(f"{self._api_url}/embeddings", payload, timeout=timeout)
        data = response.json()
        rows = data.get("data")
        if not rows:
            raise ValueError(f"Reponse embeddings {self.name} invalide")
        vectors: list[list[float]] = []
        for row in rows:
            vector = row.get("embedding") if isinstance(row, dict) else None
            if not vector:
                raise ValueError(f"Embedding {self.name} manquant")
            vectors.append(vector)
        return vectors


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"

    def __init__(self, *, api_key: str | None = None, api_url: str | None = None,
                 max_retries: int | None = None, backoff_seconds: float | None = None):
        super().__init__(
            api_key=api_key if api_key is not None else OPENAI_API_KEY,
            api_url=api_url or OPENAI_API_URL,
            max_retries=OPENAI_MAX_RETRIES if max_retries is None else max_retries,
            backoff_seconds=OPENAI_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds,
            require_api_key=True,
        )


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama par defaut (localhost:11434). Pour vLLM/LM Studio : OLLAMA_API_URL vers le
    bon serveur -- meme classe, meme protocole, seule l'URL change."""

    name = "ollama"

    def __init__(self, *, api_key: str | None = None, api_url: str | None = None,
                 max_retries: int | None = None, backoff_seconds: float | None = None):
        super().__init__(
            api_key=api_key if api_key is not None else OLLAMA_API_KEY,
            api_url=api_url or OLLAMA_API_URL,
            max_retries=OLLAMA_MAX_RETRIES if max_retries is None else max_retries,
            backoff_seconds=OLLAMA_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds,
            # Ollama ignore l'auth -- pas de vraie cle a exiger localement.
            require_api_key=False,
        )
