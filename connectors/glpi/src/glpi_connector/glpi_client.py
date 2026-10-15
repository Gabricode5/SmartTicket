"""Client REST GLPI (apirest.php).

Couvre le strict nécessaire au poller : initSession / killSession, lecture d'un ticket,
liste des tickets, ajout d'un suivi (ITILFollowup). Le transport HTTP est injectable
(`http=`) pour être testé contre des fixtures JSON sans instance GLPI réelle.

Auth GLPI : header `App-Token` (jeton applicatif) + `Authorization: user_token <token>`
sur initSession, qui renvoie un `session_token` repassé ensuite en header `Session-Token`.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from glpi_connector import config

logger = logging.getLogger(__name__)


class GlpiError(RuntimeError):
    pass


class GlpiClient:
    def __init__(
        self,
        base_url: str | None = None,
        app_token: str | None = None,
        user_token: str | None = None,
        *,
        http: Any = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or config.GLPI_URL).rstrip("/")
        self._app_token = app_token if app_token is not None else config.GLPI_APP_TOKEN
        self._user_token = user_token if user_token is not None else config.GLPI_USER_TOKEN
        self._http = http or requests.Session()
        self._timeout = timeout if timeout is not None else config.GLPI_HTTP_TIMEOUT
        self._session_token: str | None = None

    # -- bas niveau -----------------------------------------------------------------
    def _headers(self, *, with_session: bool) -> dict[str, str]:
        headers = {"App-Token": self._app_token, "Content-Type": "application/json"}
        if with_session:
            if not self._session_token:
                raise GlpiError("Session GLPI non initialisée (appelle init_session()).")
            headers["Session-Token"] = self._session_token
        return headers

    def _request(self, method: str, path: str, *, with_session: bool = True, **kwargs) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self._http.request(
            method,
            url,
            headers={**self._headers(with_session=with_session), **kwargs.pop("headers", {})},
            timeout=self._timeout,
            **kwargs,
        )
        try:
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GlpiError(f"GLPI {method} {path} -> {getattr(resp, 'status_code', '?')}: {exc}") from exc
        if resp.status_code == 204 or not (resp.content if hasattr(resp, "content") else True):
            return None
        return resp.json()

    # -- session ------------------------------------------------------------------
    def init_session(self) -> str:
        headers = {
            "App-Token": self._app_token,
            "Authorization": f"user_token {self._user_token}",
        }
        url = f"{self.base_url}/initSession"
        resp = self._http.request("GET", url, headers=headers, timeout=self._timeout)
        try:
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GlpiError(f"GLPI initSession -> {getattr(resp, 'status_code', '?')}: {exc}") from exc
        token = (resp.json() or {}).get("session_token")
        if not token:
            raise GlpiError("initSession n'a pas renvoyé de session_token.")
        self._session_token = token
        logger.info("Session GLPI ouverte.")
        return token

    def kill_session(self) -> None:
        if not self._session_token:
            return
        try:
            self._request("GET", "killSession")
        finally:
            self._session_token = None
            logger.info("Session GLPI fermée.")

    def __enter__(self) -> GlpiClient:
        self.init_session()
        return self

    def __exit__(self, *_exc) -> None:
        self.kill_session()

    # -- tickets ----------------------------------------------------------------
    def get_ticket(self, ticket_id: int) -> dict:
        return self._request("GET", f"Ticket/{ticket_id}")

    def list_tickets(
        self, *, statuses: list[int] | None = None, limit: int | None = None
    ) -> list[dict]:
        """Liste des tickets, filtrée côté client par statut si `statuses` est fourni."""
        limit = limit or config.GLPI_LIST_LIMIT
        rows = self._request(
            "GET",
            "Ticket",
            params={"range": f"0-{max(0, limit - 1)}", "sort": "id", "order": "DESC"},
        )
        rows = rows or []
        if statuses is not None:
            rows = [r for r in rows if r.get("status") in statuses]
        return rows

    def add_followup(self, ticket_id: int, content: str, *, is_private: bool) -> dict:
        """Ajoute un suivi (ITILFollowup par défaut) au ticket. APPEL D'ÉCRITURE."""
        itemtype = config.GLPI_FOLLOWUP_ITEMTYPE
        payload = {
            "input": {
                "itemtype": "Ticket",
                "items_id": ticket_id,
                "content": content,
                "is_private": 1 if is_private else 0,
            }
        }
        result = self._request("POST", itemtype, json=payload)
        if isinstance(result, list):
            result = result[0] if result else {}
        return result or {}
