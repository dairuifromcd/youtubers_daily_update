from __future__ import annotations

import json
import re
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
        sent_covers: set[str] = set()
        for message in messages:
            video_link = re.search(r"^链接：(https://www\.youtube\.com/watch\?v=([\w-]+))$", message, re.MULTILINE)
            if video_link and video_link.group(2) not in sent_covers:
                video_id = video_link.group(2)
                self._send_with_retry("sendPhoto", {
                    "photo": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    "reply_markup": {"inline_keyboard": [[{
                        "text": "观看视频", "url": video_link.group(1),
                    }]]},
                })
                sent_covers.add(video_id)
            self._send_with_retry("sendMessage", {
                "text": message, "link_preview_options": {"is_disabled": True},
            })

    def _send_with_retry(self, method: str, payload: dict) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._send_once(method, payload)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(min(2**attempt, 10))
        raise ProviderError(f"Telegram send failed after {self.max_attempts} attempts: {last_error}")

    def _send_once(self, method: str, payload: dict) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        payload = {"chat_id": self.chat_id, **payload}
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
