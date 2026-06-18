from __future__ import annotations

import json
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import ProviderError


class GeminiProviderError(ProviderError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds

    @property
    def retryable(self) -> bool:
        if self.status_code is None:
            return True
        return self.status_code == 429 or 500 <= self.status_code <= 599


class GeminiProvider:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash",
        fallback_models: tuple[str, ...] = ("gemini-2.5-flash", "gemini-2.5-flash-lite"),
        timeout_seconds: int = 60,
        max_output_tokens: int = 1200,
        max_attempts: int = 3,
        initial_backoff_seconds: float = 2.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required.")
        self.api_key = api_key
        self.model = model
        self.fallback_models = fallback_models
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.max_attempts = max_attempts
        self.initial_backoff_seconds = initial_backoff_seconds
        self.sleep_fn = sleep_fn

    def generate(self, prompt: str) -> str:
        errors: list[str] = []
        for model in self._models_to_try():
            for attempt in range(1, self.max_attempts + 1):
                try:
                    return self._generate_with_model(model, prompt)
                except GeminiProviderError as exc:
                    errors.append(f"{model} attempt {attempt}: {exc}")
                    if not exc.retryable:
                        break
                    if attempt < self.max_attempts:
                        self.sleep_fn(self._delay_seconds(attempt, exc))
            # Move to the next model only after retryable failures exhausted.
        raise ProviderError("Gemini API failed after retries: " + " | ".join(errors[-4:]))

    def _models_to_try(self) -> tuple[str, ...]:
        seen: set[str] = set()
        models: list[str] = []
        for model in (self.model, *self.fallback_models):
            clean = model.strip()
            if clean and clean not in seen:
                seen.add(clean)
                models.append(clean)
        return tuple(models)

    def _generate_with_model(self, model: str, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": self.max_output_tokens,
            },
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
            raise GeminiProviderError(
                f"Gemini API HTTP {exc.code}: {body[:300]}",
                status_code=exc.code,
                retry_after_seconds=retry_after,
            ) from exc
        except URLError as exc:
            raise GeminiProviderError(f"Gemini API network error: {exc}") from exc

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"Gemini API returned no text: {json.dumps(data)[:300]}") from exc

    def _delay_seconds(self, attempt: int, exc: GeminiProviderError) -> float:
        if exc.retry_after_seconds is not None:
            return exc.retry_after_seconds
        return self.initial_backoff_seconds * (2 ** (attempt - 1))


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return max(parsed, 0.0)
