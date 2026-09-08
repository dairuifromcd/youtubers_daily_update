from datetime import datetime, timezone
from dataclasses import replace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from youtube_daily_update.models import AppSettings, ChannelConfig, TranscriptResult, Video, RunStats
from youtube_daily_update.providers.base import ProviderError
from youtube_daily_update.providers.fake import (
    FakeLLMProvider,
    FakeNotifier,
    FakeTranscriptProvider,
    FakeYouTubeProvider,
)
from youtube_daily_update.runner import DailyUpdateProviders, DailyUpdater
from youtube_daily_update.state import SeenVideoStore


def sample_video() -> Video:
    return Video(
        video_id="vid1",
        channel_id="UC1",
        channel_name="Channel",
        title="Interesting Update",
        url="https://www.youtube.com/watch?v=vid1",
        published_at=datetime(2026, 6, 18, 3, 0, tzinfo=timezone.utc),
        description="Description",
    )


class RunnerTests(unittest.TestCase):
    def test_input_routing_uses_video_for_missing_failed_or_oversized_subtitles(self):
        cases = [(None, True), (TranscriptResult("  ", "字幕"), True),
                 (TranscriptResult("长" * 101, "字幕"), True),
                 (TranscriptResult("完整字幕", "字幕"), False),
                 (RuntimeError("subtitle unavailable"), True)]
        for transcript, use_video in cases:
            with self.subTest(transcript=transcript):
                fetcher = Mock()
                if isinstance(transcript, Exception):
                    fetcher.fetch.side_effect = transcript
                else:
                    fetcher.fetch.return_value = transcript
                llm = FakeLLMProvider()
                providers = DailyUpdateProviders(FakeYouTubeProvider(), fetcher, llm, FakeNotifier())
                with TemporaryDirectory() as tmp:
                    store = SeenVideoStore(Path(tmp) / "seen.sqlite")
                    stats = RunStats()
                    result = DailyUpdater(providers, store, AppSettings(max_transcript_chars=100))._process_video(sample_video(), stats)
                    store.close()
                self.assertEqual([sample_video().url if use_video else None], llm.video_urls)
                self.assertEqual("视频内容（Gemini直接读取）" if use_video else "字幕", result.basis)
                self.assertFalse(result.low_confidence)
                self.assertEqual([], stats.failures)

    def test_rejected_summary_is_not_sent_or_marked_seen(self):
        for failure in (ProviderError("finishReason=MAX_TOKENS"), "   "):
            with self.subTest(failure=failure):
                llm = Mock()
                if isinstance(failure, Exception):
                    llm.generate.side_effect = failure
                else:
                    llm.generate.return_value = failure
                notifier = FakeNotifier()
                providers = DailyUpdateProviders(FakeYouTubeProvider({"UC1": [sample_video()]}),
                                                 FakeTranscriptProvider(), llm, notifier)
                with TemporaryDirectory() as tmp:
                    store = SeenVideoStore(Path(tmp) / "seen.sqlite")
                    result = DailyUpdater(providers, store, AppSettings()).run(
                        [ChannelConfig(name="Channel", channel_id="UC1")],
                        now=datetime(2026, 6, 18, 2, 5, tzinfo=timezone.utc))
                    self.assertFalse(store.is_notified("vid1"))
                    store.close()
                self.assertEqual([], result.digests)
                self.assertEqual(0, result.stats.summaries_created)
                self.assertTrue(all("Interesting Update" not in m for m in notifier.messages))

    def test_short_videos_are_filtered_before_transcription_and_generation(self):
        for seconds, skipped in [(30, True), (180, True), (181, False), (None, False)]:
            with self.subTest(seconds=seconds), TemporaryDirectory() as tmp:
                video = replace(sample_video(), duration_seconds=seconds)
                transcript = Mock()
                transcript.fetch.return_value = TranscriptResult("字幕", "字幕")
                llm = FakeLLMProvider()
                providers = DailyUpdateProviders(FakeYouTubeProvider({"UC1": [video]}), transcript, llm, FakeNotifier())
                store = SeenVideoStore(Path(tmp) / "seen.sqlite")
                result = DailyUpdater(providers, store, AppSettings()).run(
                    [ChannelConfig(name="Channel", channel_id="UC1")],
                    now=datetime(2026, 6, 18, 2, 5, tzinfo=timezone.utc))
                self.assertEqual(int(skipped), result.stats.videos_skipped_short)
                self.assertEqual(int(not skipped), transcript.fetch.call_count)
                self.assertEqual(int(not skipped), len(llm.prompts))
                self.assertEqual(not skipped, store.is_notified("vid1"))
                store.close()

    def test_full_fake_run_marks_notified_and_avoids_duplicates(self):
        video = sample_video()
        youtube = FakeYouTubeProvider({"UC1": [video]})
        notifier = FakeNotifier()
        providers = DailyUpdateProviders(
            youtube=youtube,
            transcript=FakeTranscriptProvider({"vid1": TranscriptResult("transcript", "字幕")}),
            llm=FakeLLMProvider(),
            notifier=notifier,
        )
        with TemporaryDirectory() as tmp:
            store = SeenVideoStore(Path(tmp) / "seen.sqlite")
            updater = DailyUpdater(providers, store, AppSettings())
            channels = [ChannelConfig(name="Channel", channel_id="UC1")]

            first = updater.run(channels, now=datetime(2026, 6, 18, 2, 5, tzinfo=timezone.utc))
            second = updater.run(channels, now=datetime(2026, 6, 18, 2, 5, tzinfo=timezone.utc))
            store.close()

        self.assertEqual(1, first.stats.videos_marked_notified)
        self.assertEqual(1, second.stats.videos_skipped_seen)
        self.assertEqual(1, len(notifier.messages))

    def test_dry_run_does_not_notify_or_write_state(self):
        video = sample_video()
        notifier = FakeNotifier()
        providers = DailyUpdateProviders(
            youtube=FakeYouTubeProvider({"UC1": [video]}),
            transcript=FakeTranscriptProvider({"vid1": TranscriptResult("transcript", "字幕")}),
            llm=FakeLLMProvider(),
            notifier=notifier,
        )
        with TemporaryDirectory() as tmp:
            store = SeenVideoStore(Path(tmp) / "seen.sqlite")
            updater = DailyUpdater(providers, store, AppSettings(), dry_run=True)
            with redirect_stdout(StringIO()):
                result = updater.run(
                    [ChannelConfig(name="Channel", channel_id="UC1")],
                    now=datetime(2026, 6, 18, 2, 5, tzinfo=timezone.utc),
                )
            rows = store.all_rows()
            store.close()

        self.assertEqual(1, result.stats.summaries_created)
        self.assertEqual([], notifier.messages)
        self.assertEqual([], rows)

    def test_notifier_failure_does_not_mark_notified(self):
        video = sample_video()
        providers = DailyUpdateProviders(
            youtube=FakeYouTubeProvider({"UC1": [video]}),
            transcript=FakeTranscriptProvider({"vid1": TranscriptResult("transcript", "字幕")}),
            llm=FakeLLMProvider(),
            notifier=FakeNotifier(fail=True),
        )
        with TemporaryDirectory() as tmp:
            store = SeenVideoStore(Path(tmp) / "seen.sqlite")
            updater = DailyUpdater(providers, store, AppSettings())
            result = updater.run(
                [ChannelConfig(name="Channel", channel_id="UC1")],
                now=datetime(2026, 6, 18, 2, 5, tzinfo=timezone.utc),
            )
            is_notified = store.is_notified("vid1")
            store.close()

        self.assertFalse(is_notified)
        self.assertGreaterEqual(len(result.stats.failures), 1)
