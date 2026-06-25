from pathlib import Path
import unittest


class WorkflowStaticTests(unittest.TestCase):
    def test_daily_workflow_has_expected_schedule_and_manual_trigger(self):
        workflow = Path(".github/workflows/daily-update.yml").read_text(encoding="utf-8")

        self.assertEqual(workflow.count('cron: "5 2 * * *"'), 1)
        self.assertIn("02:05 UTC is 12:05 in Brisbane", workflow)
        self.assertNotIn("timezone:", workflow)
        self.assertIn("concurrency:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("YOUTUBE_API_KEY", workflow)
        self.assertIn("GEMINI_API_KEY", workflow)
        self.assertIn("TELEGRAM_BOT_TOKEN", workflow)
