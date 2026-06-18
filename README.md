# YouTube Daily Update

Daily YouTube channel monitor that summarizes new videos in Simplified Chinese and sends the digest to Telegram.

Current implementation target:

- GitHub Actions at `5 2 * * *` UTC, equal to 12:05 in Australia/Brisbane.
- YouTube Data API for video discovery.
- yt-dlp for public subtitles or automatic subtitles.
- Gemini API Free Tier for summaries.
- Telegram Bot API for notifications.
- `state/seen_videos.sqlite` for duplicate prevention.

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
- If subtitles are unavailable, summaries fall back to title and description and must be marked low confidence.
- The default Gemini model is `gemini-3.5-flash`; override it with `GEMINI_MODEL`.
