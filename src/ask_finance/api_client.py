"""Thin HTTP client used by the Gradio UI to talk to the FastAPI backend."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("ask_finance.api_client")

DEFAULT_BASE_URL = os.environ.get("ASK_FINANCE_API_URL", "http://localhost:8000")
DEFAULT_TIMEOUT = float(os.environ.get("ASK_FINANCE_API_TIMEOUT", "120"))


class ApiError(RuntimeError):
    """Raised when the backend returns a non-2xx response or is unreachable."""


class AskFinanceClient:
    """Tiny wrapper around httpx for the endpoints exposed by `ask_finance.api`."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            logger.exception("HTTP call to %s failed: %s", url, e)
            raise ApiError(f"Backend unreachable at {url}: {e}") from e
        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            raise ApiError(f"{resp.status_code} from {path}: {detail}")
        if not resp.content:
            return None
        return resp.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def roles(self) -> list[str]:
        data = self._request("GET", "/roles")
        return list(data.get("roles", []))

    def ask(
        self,
        role: str,
        message: str,
        *,
        enable_fallback: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "role": role,
            "message": message,
            "enable_fallback": enable_fallback,
        }
        return self._request("POST", "/ask", json=payload)

    def call_tool(
        self,
        name: str,
        role: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {"role": role, "args": args or {}}
        data = self._request("POST", f"/tools/{name}", json=payload)
        return data.get("result", {}) if isinstance(data, dict) else {}
