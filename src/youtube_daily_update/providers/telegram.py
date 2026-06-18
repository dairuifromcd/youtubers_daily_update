from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import ProviderError


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout_seconds: int = 30,
        max_attempts: int = 3,
    ):
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required.")
        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is required.")
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    def send_messages(self, messages: list[str]) -> None:
        for message in messages:
            self._send_with_retry(message)

    def _send_with_retry(self, message: str) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._send_once(message)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(min(2**attempt, 10))
        raise ProviderError(f"Telegram send failed after {self.max_attempts} attempts: {last_error}")

    def _send_once(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": False,
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Telegram HTTP {exc.code}: {body[:300]}") from exc
        except URLError as exc:
            raise ProviderError(f"Telegram network error: {exc}") from exc

        if not data.get("ok"):
            raise ProviderError(f"Telegram returned not ok: {json.dumps(data)[:300]}")
