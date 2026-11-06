import logging
import time

import requests

from app.config import settings

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class HttpClient:
    """Polite HTTP client: one session, a pause between requests, retries on failure."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        self._last_request = 0.0

    def get(self, url: str, params: dict | None = None) -> str:
        last_error: Exception | None = None
        for attempt in range(1, settings.request_retries + 1):
            self._pause()
            try:
                response = self._session.get(url, params=params, timeout=settings.request_timeout_seconds)
                response.raise_for_status()
                return response.text
            except requests.RequestException as exc:
                last_error = exc
                log.warning("GET %s failed (attempt %d/%d): %s", url, attempt, settings.request_retries, exc)
                time.sleep(attempt * settings.request_delay_seconds)
        raise last_error  # type: ignore[misc]

    def _pause(self) -> None:
        wait = self._last_request + settings.request_delay_seconds - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
