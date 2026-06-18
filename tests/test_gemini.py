import unittest

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
