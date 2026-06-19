from pathlib import Path
import unittest


class WorkflowStaticTests(unittest.TestCase):
    def test_daily_workflow_has_expected_schedule_and_manual_trigger(self):
        workflow = Path(".github/workflows/daily-update.yml").read_text(encoding="utf-8")

        self.assertIn('cron: "7 2 * * *"', workflow)
        self.assertIn('cron: "37 2 * * *"', workflow)
        self.assertIn('cron: "7 3 * * *"', workflow)
        self.assertIn("concurrency:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("YOUTUBE_API_KEY", workflow)
        self.assertIn("GEMINI_API_KEY", workflow)
        self.assertIn("TELEGRAM_BOT_TOKEN", workflow)
