import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from youtube_daily_update.providers.transcript_ytdlp import YtDlpTranscriptProvider, _clean_vtt


class TranscriptTests(unittest.TestCase):
    def test_note_style_and_region_blocks_do_not_discard_later_captions(self):
        for header in ("NOTE a comment", "STYLE", "REGION"):
            text = f"WEBVTT\nKind: captions\nLanguage: zh\n\n{header}\nignored\n\n00:00.000 --> 00:01.000\n正文\n"
            self.assertEqual("正文", _clean_vtt(text))

    def test_configured_language_order_wins_over_filename_sort(self):
        def download(cmd, **kwargs):
            folder = Path(cmd[cmd.index("--output") + 1]).parent
            (folder / "video.en.vtt").write_text("WEBVTT\n\nEnglish", encoding="utf-8")
            (folder / "video.zh-Hans.vtt").write_text("WEBVTT\n\n中文", encoding="utf-8")
            return SimpleNamespace(returncode=0)
        with patch("youtube_daily_update.providers.transcript_ytdlp.subprocess.run", side_effect=download):
            self.assertEqual("中文", YtDlpTranscriptProvider()._download_subtitle("url", "zh.*,en.*", False))
