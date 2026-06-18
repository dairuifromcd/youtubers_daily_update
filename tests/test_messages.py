from datetime import datetime, timezone
import unittest

from youtube_daily_update.messages import (
    build_summary_prompt,
    format_digest_messages,
    sanitize_summary_text,
    split_telegram_messages,
    validate_summary,
)
from youtube_daily_update.models import TranscriptResult, Video, VideoDigest


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
        self.assertIn("不要输出标题、频道、发布时间、链接、摘要依据、低置信度说明", prompt)
        self.assertIn("不要使用 Markdown", prompt)

    def test_summary_quality_gate_does_not_require_repeated_metadata(self):
        problems = validate_summary("- 这是中文摘要。", "标题和简介", True)

        self.assertEqual([], problems)

    def test_split_long_telegram_messages(self):
        messages = split_telegram_messages(["一" * 5000], max_chars=1000)

        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 1000 for message in messages))

    def test_sanitize_summary_removes_markdown_and_duplicate_metadata(self):
        summary = sanitize_summary_text(
            """
**摘要依据：标题和简介**
低置信度：仅基于标题和简介
* **AI供应链**：节目讨论了供应链问题。
2. 第二个重点。
"""
        )

        self.assertNotIn("**", summary)
        self.assertNotIn("摘要依据", summary)
        self.assertNotIn("低置信度", summary)
        self.assertIn("- AI供应链：节目讨论了供应链问题。", summary)
        self.assertIn("- 第二个重点。", summary)

    def test_format_digest_outputs_metadata_once(self):
        digest = VideoDigest(
            video=sample_video(),
            summary="**摘要依据：标题和简介**\n低置信度：仅基于标题和简介\n- 这是中文要点。",
            basis="标题和简介",
            low_confidence=True,
        )

        messages = format_digest_messages([digest])
        message = messages[0]

        self.assertEqual(1, message.count("摘要依据：标题和简介"))
        self.assertEqual(1, message.count("置信度：低，仅基于标题和简介"))
        self.assertNotIn("**", message)
