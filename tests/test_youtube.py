import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from youtube_daily_update.models import ChannelConfig
from youtube_daily_update.providers.youtube import YouTubeDataApiProvider, _parse_duration_seconds


class YouTubeDurationTests(unittest.TestCase):
    def test_duration_parsing(self):
        for value, expected in [("PT30S", 30), ("PT3M", 180), ("PT3M1S", 181),
                                ("PT1H2M3S", 3723), ("P1DT1S", 86401),
                                ("PT0S", 0), ("", None), ("P", None), ("invalid", None)]:
            with self.subTest(value=value):
                self.assertEqual(expected, _parse_duration_seconds(value))

    def test_api_duration_reaches_video(self):
        provider = YouTubeDataApiProvider("test")
        provider._request = Mock(side_effect=[
            {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "uploads"}}}]},
            {"items": [{"contentDetails": {"videoId": "v1"}}]},
            {"items": [{"id": "v1", "snippet": {"publishedAt": "2026-09-08T01:00:00Z", "title": "测试"},
                        "contentDetails": {"duration": "PT3M"}}]},
        ])
        videos = provider.list_recent_videos(ChannelConfig("测试", channel_id="UC1"),
            datetime(2026, 9, 8, tzinfo=timezone.utc), datetime(2026, 9, 9, tzinfo=timezone.utc), 10)
        self.assertEqual(180, videos[0].duration_seconds)
        self.assertEqual("snippet,contentDetails", provider._request.call_args.args[1]["part"])
