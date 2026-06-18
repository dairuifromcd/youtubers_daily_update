from datetime import datetime, timezone
import unittest

from youtube_daily_update.messages import (
    build_summary_prompt,
    split_telegram_messages,
    validate_summary,
)
from youtube_daily_update.models import TranscriptResult, Video


def sample_video() -> Video:
    return Video(
        video_id="vid1",
        channel_id="UC1",
        channel_name="Channel",
        title="Title",
        url="https://www.youtube.com/watch?v=vid1",
        published_at=datetime(2026, 6, 18, 3, 0, tzinfo=timezone.utc),
        description="Description",
    )


class MessageTests(unittest.TestCase):
    def test_prompt_contains_simplified_chinese_and_no_fabrication_rules(self):
        prompt = build_summary_prompt(sample_video(), TranscriptResult("hello", "字幕"), 1000)

        self.assertIn("简体中文", prompt)
        self.assertIn("不要编造", prompt)
        self.assertIn("摘要依据：字幕", prompt)

    def test_low_confidence_quality_gate(self):
        problems = validate_summary("摘要依据：标题和简介\n- 这是中文摘要。", "标题和简介", True)

        self.assertIn("summary_missing_low_confidence", problems)

    def test_split_long_telegram_messages(self):
        messages = split_telegram_messages(["一" * 5000], max_chars=1000)

        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 1000 for message in messages))
