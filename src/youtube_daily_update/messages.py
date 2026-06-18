from __future__ import annotations

import re
import textwrap
from datetime import timezone

from .models import TranscriptResult, Video, VideoDigest


TELEGRAM_MAX_CHARS = 4096
SAFE_TELEGRAM_MAX_CHARS = 3900


def metadata_transcript(video: Video) -> TranscriptResult:
    body = f"标题：{video.title}\n频道：{video.channel_name}\n简介：{video.description or '无'}"
    return TranscriptResult(text=body, source="标题和简介")


def clamp_text(text: str, max_chars: int) -> str:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "\n\n[内容已按字符预算截断]"


def build_summary_prompt(video: Video, transcript: TranscriptResult, max_chars: int) -> str:
    source_text = clamp_text(transcript.text, max_chars)
    low_confidence = transcript.source == "标题和简介"
    confidence_instruction = (
        "如果摘要依据是标题和简介，必须明确标注“低置信度：仅基于标题和简介”。"
        if low_confidence
        else "摘要依据来自字幕或自动字幕，不要声称看过视频画面。"
    )
    return textwrap.dedent(
        f"""
        请根据下面提供的 YouTube 视频信息，生成简体中文摘要。

        要求：
        - 只依据输入内容总结，不要编造未提供的信息。
        - 输出必须是简体中文。
        - 输出包含 3-5 条要点。
        - 输出包含“摘要依据：{transcript.source}”。
        - {confidence_instruction}
        - 不要声称看过视频画面，除非输入内容明确包含视觉信息。

        视频信息：
        频道：{video.channel_name}
        标题：{video.title}
        发布时间 UTC：{video.published_at.astimezone(timezone.utc).isoformat()}
        链接：{video.url}

        输入内容：
        {source_text}
        """
    ).strip()


def validate_summary(summary: str, basis: str, low_confidence: bool) -> list[str]:
    problems: list[str] = []
    stripped = summary.strip()
    if not stripped:
        problems.append("summary_empty")
    if _cjk_ratio(stripped) < 0.12:
        problems.append("summary_not_simplified_chinese_like")
    if basis not in stripped:
        problems.append("summary_missing_basis")
    if low_confidence and "低置信度" not in stripped:
        problems.append("summary_missing_low_confidence")
    return problems


def format_digest_messages(digests: list[VideoDigest], failure_count: int = 0) -> list[str]:
    if not digests and failure_count == 0:
        return []

    entries = [_format_entry(index + 1, digest) for index, digest in enumerate(digests)]
    if failure_count:
        entries.append(f"本次运行有 {failure_count} 个项目处理失败，详情见 GitHub Actions 日志。")
    return split_telegram_messages(entries)


def split_telegram_messages(entries: list[str], max_chars: int = SAFE_TELEGRAM_MAX_CHARS) -> list[str]:
    messages: list[str] = []
    current = "YouTube 今日更新\n\n"

    for entry in entries:
        block = entry.strip()
        if not block:
            continue
        addition = block + "\n\n"
        if len(current) + len(addition) <= max_chars:
            current += addition
            continue
        if current.strip():
            messages.append(current.rstrip())
        if len(addition) <= max_chars:
            current = addition
        else:
            chunks = _split_long_text(block, max_chars)
            messages.extend(chunks[:-1])
            current = chunks[-1] + "\n\n"

    if current.strip():
        messages.append(current.rstrip())
    return messages


def _format_entry(index: int, digest: VideoDigest) -> str:
    local_time = digest.video.published_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    confidence = "低置信度" if digest.low_confidence else "基于内容"
    return (
        f"{index}. {digest.video.title}\n"
        f"频道：{digest.video.channel_name}\n"
        f"发布时间：{local_time}\n"
        f"链接：{digest.video.url}\n"
        f"摘要依据：{digest.basis}（{confidence}）\n"
        f"{digest.summary.strip()}"
    )


def _split_long_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    non_space = sum(1 for char in text if not char.isspace())
    return cjk / max(non_space, 1)
