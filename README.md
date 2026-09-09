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

- Each video is sent in a separate Telegram message with its own explicitly selected large YouTube link preview above the text. Long summaries are split with the video link retained on each part; failure notices are separate. Preview availability is controlled by Telegram/YouTube. This does not add Gemini calls.
- No full transcript or full summary is stored in SQLite.
- Complete subtitles are preferred. If extraction fails, returns empty text, or exceeds `max_transcript_chars`, Gemini receives the YouTube video URL as native video input instead of title/description or a truncated transcript. The digest identifies its actual source.
- Summaries target 1,000–1,500 Chinese characters (shorter for simple videos), with a main idea and 4–7 themed points preserving evidence, key numbers, chronology and the author's qualifications. Promotions and repetitive details are omitted. Length is a prompt target, not a hard text cutoff.
- Gemini's output budget is 8,192 tokens, including thinking, with a 180-second request timeout. Only `finishReason=STOP` with non-empty answer text is accepted; thinking parts are excluded. Truncated, blocked and empty responses are rejected without an automatic extra generation or model fallback. Failed videos are not marked notified; the existing daily discovery window still applies to future retries.
- Normal processing uses one generation per video; existing transient API retries/model fallbacks still apply. Native video input can consume substantially more quota than subtitles. This change does not alter Google billing settings or the configured 20-video per-run limit. Available free capacity depends on the project's actual Google quota and video durations.
- Logs include input source, returned model version, finish reason and token usage for troubleshooting. Invalid summaries generate a failure notice rather than a partial video digest.
- The default Gemini model is `gemini-3.5-flash`; override it with `GEMINI_MODEL`.
- Override fallback models with `GEMINI_FALLBACK_MODELS`, using a comma-separated list.
- GitHub scheduled workflows can start hours late. The workflow is intentionally triggered at `21:05 UTC` and waits until `12:05 Australia/Brisbane` before doing the real work.

### 摘要与短视频过滤

每个视频保留一个主旨和 3–5 条核心要点，目标约 600–900 字（简单内容更短），并单独显示封面。发送前清理重复的通用“主题：”标签和完全相同的段落。

`settings.short_video_max_seconds` 默认 180：根据 YouTube API 时长跳过不超过 3 分钟的视频，在字幕抓取及 Gemini 调用之前过滤，不占模型调用次数。设为 0 可关闭。此规则按时长过滤，也会排除短横屏视频；时长未知的视频继续正常处理。

Gemini 连接或读取超时会进入已有的有限重试与备用模型流程；重试可能额外消耗模型配额，仍失败时会报告失败，不发布不完整摘要。

封面以独立图片发送，带“观看视频”按钮，随后发送完整摘要并关闭链接预览，避免自动卡片夹带频道简介广告。长摘要分段时同一视频只发送一次封面。主旨目标 40–80 字、1–2 句，正文保留摘要来源，不再展示笼统的置信度标签。
