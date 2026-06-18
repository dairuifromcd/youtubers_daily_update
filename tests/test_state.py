from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from youtube_daily_update.models import Video
from youtube_daily_update.state import SeenVideoStore


class StateTests(unittest.TestCase):
    def test_mark_notified_without_transcript_persistence(self):
        video = Video(
            video_id="vid1",
            channel_id="UC1",
            channel_name="Channel",
            title="Title",
            url="https://www.youtube.com/watch?v=vid1",
            published_at=datetime(2026, 6, 18, 3, 0, tzinfo=timezone.utc),
            description="Description",
        )
        with TemporaryDirectory() as tmp:
            store = SeenVideoStore(Path(tmp) / "seen.sqlite")
            self.assertFalse(store.is_notified("vid1"))
            store.mark_notified(video, summary_basis="字幕", summary_chars=120)
            self.assertTrue(store.is_notified("vid1"))
            rows = store.all_rows()
            store.close()

        self.assertEqual(1, len(rows))
        self.assertNotIn("transcript", rows[0].keys())
        self.assertNotIn("summary", rows[0].keys())
