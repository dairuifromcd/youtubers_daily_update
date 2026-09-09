import io
import json
import unittest
from unittest.mock import patch

from youtube_daily_update.providers.telegram import TelegramNotifier


class TelegramTests(unittest.TestCase):
    def test_covers_once_per_video_and_no_ad_previews(self):
        messages = ["链接：https://www.youtube.com/watch?v=vid1\n摘要",
                    "链接：https://www.youtube.com/watch?v=vid1\n续文",
                    "链接：https://www.youtube.com/watch?v=vid2\n摘要",
                    "本次运行有 1 个项目处理失败"]
        with patch("youtube_daily_update.providers.telegram.urlopen",
                   side_effect=lambda *a, **kw: io.BytesIO(b'{"ok":true}')) as send:
            TelegramNotifier("test-token", "test-chat").send_messages(messages)
        calls = [(c.args[0].full_url.rsplit("/", 1)[-1], json.loads(c.args[0].data)) for c in send.call_args_list]
        self.assertEqual(["sendPhoto", "sendMessage", "sendMessage", "sendPhoto", "sendMessage", "sendMessage"], [m for m, p in calls])
        photos = [p for m, p in calls if m == "sendPhoto"]
        self.assertEqual(["https://i.ytimg.com/vi/vid1/hqdefault.jpg", "https://i.ytimg.com/vi/vid2/hqdefault.jpg"], [p["photo"] for p in photos])
        self.assertEqual("https://www.youtube.com/watch?v=vid1", photos[0]["reply_markup"]["inline_keyboard"][0][0]["url"])
        texts = [p for m, p in calls if m == "sendMessage"]
        self.assertEqual(messages, [p["text"] for p in texts])
        self.assertTrue(all(p["link_preview_options"]["is_disabled"] for p in texts))

    def test_text_retry_does_not_resend_successful_cover(self):
        with patch("youtube_daily_update.providers.telegram.urlopen", side_effect=[
                io.BytesIO(b'{"ok":true}'), TimeoutError(), io.BytesIO(b'{"ok":true}')]) as send, \
                patch("youtube_daily_update.providers.telegram.time.sleep"):
            TelegramNotifier("test-token", "test-chat").send_messages(["链接：https://www.youtube.com/watch?v=vid1"])
        self.assertEqual(["sendPhoto", "sendMessage", "sendMessage"],
                         [c.args[0].full_url.rsplit("/", 1)[-1] for c in send.call_args_list])
