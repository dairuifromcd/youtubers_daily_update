from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models import ChannelConfig, TranscriptResult, Video


class ProviderError(RuntimeError):
    pass


class YouTubeProvider(Protocol):
    def list_recent_videos(
        self,
        channel: ChannelConfig,
        start_utc: datetime,
        end_utc: datetime,
        max_results: int,
    ) -> list[Video]:
        ...


class TranscriptProvider(Protocol):
    def fetch(self, video: Video, preferred_languages: tuple[str, ...]) -> TranscriptResult | None:
        ...


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class Notifier(Protocol):
    def send_messages(self, messages: list[str]) -> None:
        ...
