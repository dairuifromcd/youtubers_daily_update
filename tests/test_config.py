from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from youtube_daily_update.config import ConfigError, load_project_config


class ConfigTests(unittest.TestCase):
    def test_load_channels_and_settings(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "channels.yml"
            path.write_text(
                """
settings:
  max_videos_per_run: 3
channels:
  - name: Enabled
    channel_id: UC12345678901234567890
    enabled: true
  - name: Disabled
    url: https://www.youtube.com/@disabled
    enabled: false
""",
                encoding="utf-8",
            )

            channels, settings = load_project_config(path)

        self.assertEqual(2, len(channels))
        self.assertTrue(channels[0].enabled)
        self.assertFalse(channels[1].enabled)
        self.assertEqual(3, settings.max_videos_per_run)

    def test_enabled_channel_requires_id_or_url(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "channels.yml"
            path.write_text("channels:\n  - name: Broken\n", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_project_config(path)
