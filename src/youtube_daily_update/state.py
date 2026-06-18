from __future__ import annotations

import sqlite3
from datetime import timezone
from pathlib import Path

from .models import Video, utc_now


class SeenVideoStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_videos (
                video_id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                channel_name TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                published_at TEXT NOT NULL,
                status TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                summary_basis TEXT,
                summary_chars INTEGER DEFAULT 0
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_processed_videos_status
            ON processed_videos(status)
            """
        )
        self._conn.commit()

    def is_notified(self, video_id: str) -> bool:
        row = self._conn.execute(
            "SELECT status FROM processed_videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        return bool(row and row["status"] == "notified")

    def mark_notified(self, video: Video, summary_basis: str, summary_chars: int) -> None:
        now = utc_now().astimezone(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO processed_videos (
                video_id, channel_id, channel_name, title, url, published_at,
                status, processed_at, summary_basis, summary_chars
            )
            VALUES (?, ?, ?, ?, ?, ?, 'notified', ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                channel_name = excluded.channel_name,
                title = excluded.title,
                url = excluded.url,
                published_at = excluded.published_at,
                status = 'notified',
                processed_at = excluded.processed_at,
                summary_basis = excluded.summary_basis,
                summary_chars = excluded.summary_chars
            """,
            (
                video.video_id,
                video.channel_id,
                video.channel_name,
                video.title,
                video.url,
                video.published_at.astimezone(timezone.utc).isoformat(),
                now,
                summary_basis,
                summary_chars,
            ),
        )
        self._conn.commit()

    def all_rows(self) -> list[sqlite3.Row]:
        return list(self._conn.execute("SELECT * FROM processed_videos ORDER BY video_id"))
