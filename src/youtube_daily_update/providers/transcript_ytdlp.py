from __future__ import annotations

import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ..models import TranscriptResult, Video


class YtDlpTranscriptProvider:
    def __init__(self, executable: str = "yt-dlp", timeout_seconds: int = 120):
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def fetch(self, video: Video, preferred_languages: tuple[str, ...]) -> TranscriptResult | None:
        languages = ",".join(preferred_languages)
        manual = self._download_subtitle(video.url, languages, auto=False)
        if manual:
            return TranscriptResult(text=manual, source="字幕")
        automatic = self._download_subtitle(video.url, languages, auto=True)
        if automatic:
            return TranscriptResult(text=automatic, source="自动字幕")
        return None

    def _download_subtitle(self, url: str, languages: str, auto: bool) -> str | None:
        with TemporaryDirectory() as tmp:
            output_template = str(Path(tmp) / "%(id)s.%(ext)s")
            cmd = [
                self.executable,
                "--skip-download",
                "--no-playlist",
                "--sub-langs",
                languages,
                "--sub-format",
                "vtt",
                "--output",
                output_template,
            ]
            cmd.append("--write-auto-subs" if auto else "--write-subs")
            cmd.append(url)
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                return None
            files = sorted(Path(tmp).glob("*.vtt"))
            if not files:
                return None
            return _clean_vtt(files[0].read_text(encoding="utf-8", errors="replace"))


def _clean_vtt(text: str) -> str:
    lines: list[str] = []
    previous = ""
    skip_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == "WEBVTT":
            continue
        if line.startswith(("NOTE", "STYLE", "REGION")):
            skip_block = True
            continue
        if skip_block:
            if not line:
                skip_block = False
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line and line != previous:
            lines.append(line)
            previous = line
    return "\n".join(lines).strip()
