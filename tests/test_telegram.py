import io
import json
import unittest
from unittest.mock import patch

from youtube_daily_update.providers.telegram import TelegramNotifier


class TelegramTests(unittest.TestCase):
    def test_explicit_large_preview_for_video_and_none_for_failure_notice(self):
        for message, expected in [
            ("YouTube 今日更新\n链接：https://www.youtube.com/watch?v=vid1\n\n摘要", {
                "is_disabled": False, "url": "https://www.youtube.com/watch?v=vid1",
                "prefer_large_media": True, "show_above_text": True}),
            ("本次运行有 1 个项目处理失败", {"is_disabled": True}),
        ]:
            with self.subTest(message=message):
                with patch("youtube_daily_update.providers.telegram.urlopen",
                           return_value=io.BytesIO(b'{"ok":true}')) as send:
                    TelegramNotifier("test-token", "test-chat")._send_once(message)
                payload = json.loads(send.call_args.args[0].data)
                self.assertEqual(expected, payload["link_preview_options"])
                self.assertEqual(message, payload["text"])
