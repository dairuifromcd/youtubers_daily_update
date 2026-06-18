from __future__ import annotations

from datetime import datetime

from ..models import ChannelConfig, TranscriptResult, Video


class FakeYouTubeProvider:
    def __init__(self, videos_by_channel: dict[str, list[Video]] | None = None):
        self.videos_by_channel = videos_by_channel or {}
        self.calls: list[str] = []

    def list_recent_videos(
        self,
        channel: ChannelConfig,
        start_utc: datetime,
        end_utc: datetime,
        max_results: int,
    ) -> list[Video]:
        key = channel.channel_id or channel.url or channel.name
        self.calls.append(key)
        videos = self.videos_by_channel.get(key, [])
        filtered = [
            video
            for video in videos
            if start_utc <= video.published_at.astimezone(start_utc.tzinfo) < end_utc
        ]
        return filtered[:max_results]


class FakeTranscriptProvider:
    def __init__(self, transcripts: dict[str, TranscriptResult | None] | None = None):
        self.transcripts = transcripts or {}
        self.calls: list[str] = []

    def fetch(self, video: Video, preferred_languages: tuple[str, ...]) -> TranscriptResult | None:
        self.calls.append(video.video_id)
        return self.transcripts.get(video.video_id)


class FakeLLMProvider:
    def __init__(self, summaries: dict[str, str] | None = None, default_summary: str | None = None):
        self.summaries = summaries or {}
        self.default_summary = default_summary or (
            "- 这个视频介绍了主要更新。\n"
            "- 内容包含几个值得关注的重点。\n"
            "- 适合想快速了解主题的观众。"
        )
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        for key, summary in self.summaries.items():
            if key in prompt:
                return summary
        return self.default_summary


class FakeNotifier:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.messages: list[str] = []

    def send_messages(self, messages: list[str]) -> None:
        if self.fail:
            raise RuntimeError("fake notifier failed")
        self.messages.extend(messages)
