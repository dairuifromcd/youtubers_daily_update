import unittest
import io
import json
from unittest.mock import patch

from youtube_daily_update.providers.base import ProviderError
from youtube_daily_update.providers.gemini import GeminiProvider, GeminiProviderError


class StubGeminiProvider(GeminiProvider):
    def __init__(self, failures_before_success: int = 0, fail_primary: bool = False):
        super().__init__(
            "test-key",
            model="primary",
            fallback_models=("fallback",),
            max_attempts=2,
            initial_backoff_seconds=0,
            sleep_fn=lambda _: None,
        )
        self.failures_before_success = failures_before_success
        self.fail_primary = fail_primary
        self.calls: list[str] = []

    def _generate_with_model(self, model: str, prompt: str) -> str:
        self.calls.append(model)
        if self.fail_primary and model == "primary":
            raise GeminiProviderError("busy", status_code=503)
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise GeminiProviderError("busy", status_code=503)
        return f"ok from {model}"


class GeminiProviderTests(unittest.TestCase):
    def test_video_payload_and_answer_parts(self):
        data = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "private reasoning", "thought": True},
            {"text": "中文主旨"}, {"text": "详细要点"},
        ]}}]}
        with patch("youtube_daily_update.providers.gemini.urlopen",
                   return_value=io.BytesIO(json.dumps(data).encode())) as request:
            result = GeminiProvider("test-key").generate("总结", video_url="https://www.youtube.com/watch?v=TI-Qa30nyjY")
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual("中文主旨\n详细要点", result)
        self.assertEqual(8192, payload["generationConfig"]["maxOutputTokens"])
        self.assertEqual("video/mp4", payload["contents"][0]["parts"][0]["fileData"]["mimeType"])

    def test_incomplete_or_empty_response_is_not_retried_or_returned(self):
        for reason, parts in [("MAX_TOKENS", [{"text": "partial"}]),
                              ("SAFETY", [{"text": "partial"}]),
                              (None, [{"text": "partial"}]),
                              ("STOP", [{"text": "thinking", "thought": True}]),
                              ("STOP", [])]:
            with self.subTest(reason=reason, parts=parts):
                data = {"candidates": [{"finishReason": reason, "content": {"parts": parts}}]}
                with patch("youtube_daily_update.providers.gemini.urlopen",
                           return_value=io.BytesIO(json.dumps(data).encode())) as request:
                    with self.assertRaises(ProviderError):
                        GeminiProvider("test-key").generate("总结")
                    self.assertEqual(1, request.call_count)

    def test_read_timeout_retries_and_remains_bounded(self):
        data = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "中文摘要"}]}}]}
        provider = GeminiProvider("test-key", fallback_models=(), max_attempts=2, sleep_fn=lambda _: None)
        with patch("youtube_daily_update.providers.gemini.urlopen",
                   side_effect=[TimeoutError("read timed out"), io.BytesIO(json.dumps(data).encode())]) as request:
            self.assertEqual("中文摘要", provider.generate("总结"))
            self.assertEqual(2, request.call_count)
        with patch("youtube_daily_update.providers.gemini.urlopen", side_effect=TimeoutError) as request:
            with self.assertRaises(ProviderError):
                provider.generate("总结")
            self.assertEqual(2, request.call_count)

    def test_retries_transient_503(self):
        provider = StubGeminiProvider(failures_before_success=1)

        result = provider.generate("prompt")

        self.assertEqual("ok from primary", result)
        self.assertEqual(["primary", "primary"], provider.calls)

    def test_uses_fallback_after_primary_retries_exhausted(self):
        provider = StubGeminiProvider(fail_primary=True)

        result = provider.generate("prompt")

        self.assertEqual("ok from fallback", result)
        self.assertEqual(["primary", "primary", "fallback"], provider.calls)

    def test_raises_after_all_models_fail(self):
        provider = StubGeminiProvider(fail_primary=True)
        provider.fallback_models = ()

        with self.assertRaises(ProviderError):
            provider.generate("prompt")
