from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


BRISBANE_TZ_NAME = "Australia/Brisbane"


def parse_rfc3339(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ChannelConfig:
    name: str
    enabled: bool = True
    channel_id: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class AppSettings:
    state_path: str = "state/seen_videos.sqlite"
    max_videos_per_channel: int = 10
    max_videos_per_run: int = 20
    max_transcript_chars: int = 50000
    preferred_subtitle_languages: tuple[str, ...] = ("zh.*", "en.*")


@dataclass(frozen=True)
class Video:
    video_id: str
    channel_id: str
    channel_name: str
    title: str
    url: str
    published_at: datetime
    description: str = ""


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    source: str


@dataclass(frozen=True)
class VideoDigest:
    video: Video
    summary: str
    basis: str
    low_confidence: bool = False


@dataclass
class RunStats:
    channels_total: int = 0
    channels_checked: int = 0
    videos_found: int = 0
    videos_skipped_seen: int = 0
    summaries_created: int = 0
    messages_sent: int = 0
    videos_marked_notified: int = 0
    failures: list[str] = field(default_factory=list)

    def add_failure(self, message: str) -> None:
        self.failures.append(message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "channels_total": self.channels_total,
            "channels_checked": self.channels_checked,
            "videos_found": self.videos_found,
            "videos_skipped_seen": self.videos_skipped_seen,
            "summaries_created": self.summaries_created,
            "messages_sent": self.messages_sent,
            "videos_marked_notified": self.videos_marked_notified,
            "failure_count": len(self.failures),
        }
