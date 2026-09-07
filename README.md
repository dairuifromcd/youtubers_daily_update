# YouTube Daily Update

Daily YouTube channel monitor that summarizes new videos in Simplified Chinese and sends the digest to Telegram.

Current implementation target:

- GitHub Actions scheduled early each day, then waits in the runner until 12:05 in Australia/Brisbane before checking YouTube.
- YouTube Data API for video discovery.
- yt-dlp for public subtitles or automatic subtitles.
- Gemini API Free Tier for summaries.
- Telegram Bot API for notifications.
- `state/seen_videos.sqlite` for duplicate prevention.
- Gemini retries transient `429` and `5xx` errors, then falls back to `gemini-2.5-flash` and `gemini-2.5-flash-lite`.

## Setup

1. Edit `channels.yml`.

   Prefer `channel_id` when possible because it avoids extra YouTube API lookup:

   ```yaml
   channels:
     - name: Example Channel
       channel_id: UCxxxxxxxxxxxxxxxxxxxxxx
       enabled: true
   ```

2. Add GitHub repository secrets:

   - `YOUTUBE_API_KEY`
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

3. Keep the repository private if committing `state/seen_videos.sqlite`.

## Local Commands

Run tests:

```bash
python -m unittest discover
```

Run with fake providers and no network:

```bash
PYTHONPATH=src python -m youtube_daily_update --provider fake --dry-run
```

Run a real dry-run without sending Telegram:

```bash
YOUTUBE_API_KEY=... GEMINI_API_KEY=... \
PYTHONPATH=src python -m youtube_daily_update --dry-run
```

Run for real:

```bash
YOUTUBE_API_KEY=... GEMINI_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
PYTHONPATH=src python -m youtube_daily_update
```

## Notes

- No full transcript or full summary is stored in SQLite.
- Complete subtitles are preferred. If extraction fails, returns empty text, or exceeds `max_transcript_chars`, Gemini receives the YouTube video URL as native video input instead of title/description or a truncated transcript. The digest identifies its actual source.
- Summaries target 1,000–1,500 Chinese characters (shorter for simple videos), with a main idea and 4–7 themed points preserving evidence, key numbers, chronology and the author's qualifications. Promotions and repetitive details are omitted. Length is a prompt target, not a hard text cutoff.
- Gemini's output budget is 8,192 tokens, including thinking, with a 180-second request timeout. Only `finishReason=STOP` with non-empty answer text is accepted; thinking parts are excluded. Truncated, blocked and empty responses are rejected without an automatic extra generation or model fallback. Failed videos are not marked notified; the existing daily discovery window still applies to future retries.
- Normal processing uses one generation per video; existing transient API retries/model fallbacks still apply. Native video input can consume substantially more quota than subtitles. This change does not alter Google billing settings or the configured 20-video per-run limit. Available free capacity depends on the project's actual Google quota and video durations.
- Logs include input source, returned model version, finish reason and token usage for troubleshooting. Invalid summaries generate a failure notice rather than a partial video digest.
- The default Gemini model is `gemini-3.5-flash`; override it with `GEMINI_MODEL`.
- Override fallback models with `GEMINI_FALLBACK_MODELS`, using a comma-separated list.
- GitHub scheduled workflows can start hours late. The workflow is intentionally triggered at `21:05 UTC` and waits until `12:05 Australia/Brisbane` before doing the real work.
