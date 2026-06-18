from datetime import datetime, timezone
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from youtube_daily_update.models import AppSettings, ChannelConfig, TranscriptResult, Video
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
