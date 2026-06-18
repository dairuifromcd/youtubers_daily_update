from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from .messages import (
    build_summary_prompt,
    format_digest_messages,
    metadata_transcript,
    validate_summary,
)
from .models import AppSettings, ChannelConfig, RunStats, TranscriptResult, VideoDigest
from .providers.base import LLMProvider, Notifier, TranscriptProvider, YouTubeProvider
from .state import SeenVideoStore
from .time_window import brisbane_day_window


LOGGER = logging.getLogger(__name__)


@dataclass
class DailyUpdateProviders:
    youtube: YouTubeProvider
    transcript: TranscriptProvider
    llm: LLMProvider
    notifier: Notifier


@dataclass
class RunResult:
    stats: RunStats
    messages: list[str]
    digests: list[VideoDigest]


class DailyUpdater:
    def __init__(
        self,
        providers: DailyUpdateProviders,
        store: SeenVideoStore,
        settings: AppSettings,
        dry_run: bool = False,
    ):
        self.providers = providers
        self.store = store
        self.settings = settings
        self.dry_run = dry_run

    def run(self, channels: list[ChannelConfig], now: datetime | None = None) -> RunResult:
        enabled_channels = [channel for channel in channels if channel.enabled]
        stats = RunStats(channels_total=len(enabled_channels))
        start_utc, end_utc = brisbane_day_window(now)
        digests: list[VideoDigest] = []

        for channel in enabled_channels:
            stats.channels_checked += 1
            try:
                videos = self.providers.youtube.list_recent_videos(
                    channel,
                    start_utc,
                    end_utc,
                    max_results=self.settings.max_videos_per_channel,
                )
            except Exception as exc:  # noqa: BLE001 - provider failures must not stop the run.
                stats.add_failure(f"YouTube channel failed: {channel.name}: {exc}")
                LOGGER.exception("youtube_channel_failed", extra={"channel": channel.name})
                continue

            for video in videos:
                if len(digests) >= self.settings.max_videos_per_run:
                    break
                stats.videos_found += 1
                if self.store.is_notified(video.video_id):
                    stats.videos_skipped_seen += 1
                    continue

                digest = self._process_video(video, stats)
                if digest is not None:
                    digests.append(digest)
                    stats.summaries_created += 1

        messages = format_digest_messages(digests, failure_count=len(stats.failures))
        if self.dry_run:
            for message in messages:
                print(message)
        elif messages:
            try:
                self.providers.notifier.send_messages(messages)
                stats.messages_sent = len(messages)
                for digest in digests:
                    self.store.mark_notified(
                        digest.video,
                        summary_basis=digest.basis,
                        summary_chars=len(digest.summary),
                    )
                    stats.videos_marked_notified += 1
            except Exception as exc:  # noqa: BLE001
                stats.add_failure(f"Telegram notification failed: {exc}")
                LOGGER.error("telegram_notification_failed: %s", exc)

        LOGGER.info("run_stats %s", json.dumps(stats.as_dict(), ensure_ascii=False))
        return RunResult(stats=stats, messages=messages, digests=digests)

    def _process_video(self, video, stats: RunStats) -> VideoDigest | None:
        try:
            transcript = self.providers.transcript.fetch(
                video, self.settings.preferred_subtitle_languages
            )
        except Exception as exc:  # noqa: BLE001
            stats.add_failure(f"Transcript failed for {video.video_id}: {exc}")
            LOGGER.warning("transcript_failed", exc_info=True, extra={"video_id": video.video_id})
            transcript = None

        if transcript is None or not transcript.text.strip():
            transcript = metadata_transcript(video)

        low_confidence = transcript.source == "标题和简介"
        prompt = build_summary_prompt(
            video, transcript, max_chars=self.settings.max_transcript_chars
        )

        try:
            summary = self.providers.llm.generate(prompt).strip()
        except Exception as exc:  # noqa: BLE001
            stats.add_failure(f"Gemini failed for {video.video_id}: {exc}")
            LOGGER.exception("llm_failed", extra={"video_id": video.video_id})
            return None

        problems = validate_summary(summary, transcript.source, low_confidence)
        if problems:
            stats.add_failure(f"Summary quality warning for {video.video_id}: {','.join(problems)}")
            LOGGER.warning(
                "summary_quality_warning",
                extra={"video_id": video.video_id, "problems": ",".join(problems)},
            )

        return VideoDigest(
            video=video,
            summary=summary,
            basis=transcript.source,
            low_confidence=low_confidence,
        )
