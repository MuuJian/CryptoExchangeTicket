"""Small, reusable HTTP helpers for exchange APIs."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import requests


RETRYABLE_STATUS_CODES = frozenset({418, 429, 500, 502, 503, 504})


class JsonHttpClient:
    """Thread-safe JSON client with one requests session per worker thread."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], requests.Session] = requests.Session,
        sleep: Callable[[float], None] = time.sleep,
        retry_base_delay: float = 1.0,
    ) -> None:
        self._session_factory = session_factory
        self._sleep = sleep
        self._retry_base_delay = retry_base_delay
        self._thread_local = threading.local()

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float = 10,
        attempts: int = 3,
    ) -> Any:
        """GET *url* and decode JSON, retrying transient request failures."""
        if attempts <= 0:
            raise ValueError("attempts must be greater than 0")

        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = self._session().get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt == attempts or not self._should_retry(exc):
                    break
                self._sleep(self._retry_delay(attempt, exc))

        assert last_error is not None
        raise last_error

    def _session(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = self._session_factory()
            self._thread_local.session = session
        return session

    def _should_retry(self, exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        return response is None or response.status_code in RETRYABLE_STATUS_CODES

    def _retry_delay(self, attempt: int, exc: Exception) -> float:
        response = getattr(exc, "response", None)
        if response is not None and response.status_code in {418, 429}:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), 2.0 * attempt)
                except ValueError:
                    pass
            return 10.0 * attempt
        return self._retry_base_delay * attempt


default_client = JsonHttpClient()
