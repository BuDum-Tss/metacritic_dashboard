import logging
import time

import requests

from app.config import settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMClient:
    """Chat completions over an OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float, retries: int) -> None:
        self.model = model
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._timeout = timeout
        self._retries = retries

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 4000,  # the analysis of every review comes before the points
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            if attempt:
                time.sleep(2 * attempt)
            try:
                response = requests.post(self._url, json=body, headers=self._headers, timeout=self._timeout)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise LLMError(f"HTTP {response.status_code}")
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                if not content:
                    raise LLMError("empty answer")
                return content
            except (requests.RequestException, LLMError, KeyError, IndexError, ValueError) as exc:
                last_error = exc
                log.warning("LLM request failed (attempt %d/%d): %s", attempt + 1, self._retries + 1, exc)
        raise LLMError(str(last_error))


def make_llm_client() -> LLMClient | None:
    """The client from the settings, or None when no API key is set (summaries are then off)."""
    if not settings.llm_api_key:
        return None
    return LLMClient(
        settings.llm_api_key,
        settings.llm_base_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.llm_retries,
    )
