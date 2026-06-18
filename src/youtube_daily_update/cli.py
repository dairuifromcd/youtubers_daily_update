from __future__ import annotations

import argparse
import os
from datetime import datetime

from .config import load_project_config
from .logging_utils import configure_logging
from .models import AppSettings
from .providers.fake import FakeLLMProvider, FakeNotifier, FakeTranscriptProvider, FakeYouTubeProvider
from .providers.gemini import GeminiProvider
from .providers.telegram import TelegramNotifier
from .providers.transcript_ytdlp import YtDlpTranscriptProvider
from .providers.youtube import YouTubeDataApiProvider
from .runner import DailyUpdateProviders, DailyUpdater
from .state import SeenVideoStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send daily YouTube updates to Telegram.")
    parser.add_argument("--config", default="channels.yml")
    parser.add_argument("--state", default=None)
    parser.add_argument("--provider", choices=("real", "fake"), default="real")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--now", default=None, help="ISO datetime override for tests or replay.")
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument("--max-videos-per-run", type=int, default=None)
    parser.add_argument("--max-transcript-chars", type=int, default=None)
    args = parser.parse_args(argv)

    secrets = [
        os.environ.get("GEMINI_API_KEY", ""),
        os.environ.get("YOUTUBE_API_KEY", ""),
        os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        os.environ.get("TELEGRAM_CHAT_ID", ""),
    ]
    configure_logging(args.log_level, secrets=secrets)

    channels, settings = load_project_config(args.config)
    settings = _override_settings(settings, args)

    enabled_channels = [channel for channel in channels if channel.enabled]
    if args.provider == "real" and enabled_channels:
        _require_env("YOUTUBE_API_KEY")
        _require_env("GEMINI_API_KEY")
        if not args.dry_run:
            _require_env("TELEGRAM_BOT_TOKEN")
            _require_env("TELEGRAM_CHAT_ID")

    providers = (
        _build_providers(args.provider, dry_run=args.dry_run)
        if enabled_channels
        else _build_providers("fake", dry_run=True)
    )
    store = SeenVideoStore(args.state or settings.state_path)
    try:
        now = _parse_now(args.now)
        updater = DailyUpdater(providers=providers, store=store, settings=settings, dry_run=args.dry_run)
        updater.run(channels, now=now)
    finally:
        store.close()
    return 0


def _build_providers(provider: str, dry_run: bool) -> DailyUpdateProviders:
    if provider == "fake":
        return DailyUpdateProviders(
            youtube=FakeYouTubeProvider(),
            transcript=FakeTranscriptProvider(),
            llm=FakeLLMProvider(),
            notifier=FakeNotifier(),
        )

    return DailyUpdateProviders(
        youtube=YouTubeDataApiProvider(os.environ.get("YOUTUBE_API_KEY", "")),
        transcript=YtDlpTranscriptProvider(),
        llm=GeminiProvider(
            os.environ.get("GEMINI_API_KEY", ""),
            model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
        ),
        notifier=FakeNotifier() if dry_run else TelegramNotifier(
            os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            os.environ.get("TELEGRAM_CHAT_ID", ""),
        ),
    )


def _override_settings(settings: AppSettings, args: argparse.Namespace) -> AppSettings:
    return AppSettings(
        state_path=args.state or settings.state_path,
        max_videos_per_channel=settings.max_videos_per_channel,
        max_videos_per_run=args.max_videos_per_run or settings.max_videos_per_run,
        max_transcript_chars=args.max_transcript_chars or settings.max_transcript_chars,
        preferred_subtitle_languages=settings.preferred_subtitle_languages,
    )


def _require_env(name: str) -> None:
    if not os.environ.get(name):
        raise RuntimeError(f"Missing required environment variable: {name}")


def _parse_now(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)
