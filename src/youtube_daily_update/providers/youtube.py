from __future__ import annotations

import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from ..models import ChannelConfig, Video, parse_rfc3339
from ..time_window import is_in_window
from .base import ProviderError


class YouTubeDataApiProvider:
    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, timeout_seconds: int = 30):
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is required.")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def list_recent_videos(
        self,
        channel: ChannelConfig,
        start_utc: datetime,
        end_utc: datetime,
        max_results: int,
    ) -> list[Video]:
        channel_id = self._resolve_channel_id(channel)
        channel_info = self._get_channel_info(channel_id)
        uploads_playlist = channel_info["contentDetails"]["relatedPlaylists"]["uploads"]
        playlist_items = self._request(
            "playlistItems",
            {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist,
                "maxResults": min(max_results, 50),
            },
        ).get("items", [])

        video_ids = [
            item.get("contentDetails", {}).get("videoId")
            or item.get("snippet", {}).get("resourceId", {}).get("videoId")
            for item in playlist_items
        ]
        video_ids = [video_id for video_id in video_ids if video_id]
        details = self._get_video_details(video_ids)

        videos: list[Video] = []
        for video_id in video_ids:
            snippet = details.get(video_id)
            if not snippet:
                continue
            published_at = parse_rfc3339(snippet["publishedAt"])
            if not is_in_window(published_at, start_utc, end_utc):
                continue
            videos.append(
                Video(
                    video_id=video_id,
                    channel_id=snippet.get("channelId", channel_id),
                    channel_name=snippet.get("channelTitle") or channel.name,
                    title=snippet.get("title", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=published_at,
                    description=snippet.get("description", ""),
                )
            )
        return videos

    def _resolve_channel_id(self, channel: ChannelConfig) -> str:
        if channel.channel_id:
            return channel.channel_id
        if not channel.url:
            raise ProviderError(f"Channel {channel.name} has no channel_id or url.")

        direct = _extract_channel_id(channel.url)
        if direct:
            return direct

        handle = _extract_handle(channel.url)
        if handle:
            try:
                data = self._request(
                    "channels",
                    {"part": "id", "forHandle": handle},
                )
                items = data.get("items", [])
                if items:
                    return items[0]["id"]
            except ProviderError:
                pass

            data = self._request(
                "search",
                {
                    "part": "snippet",
                    "type": "channel",
                    "q": f"@{handle}",
                    "maxResults": 1,
                },
            )
            items = data.get("items", [])
            if items:
                return items[0]["snippet"]["channelId"]

        raise ProviderError(
            f"Could not resolve channel id for {channel.name}. Prefer channel_id in channels.yml."
        )

    def _get_channel_info(self, channel_id: str) -> dict:
        data = self._request(
            "channels",
            {"part": "snippet,contentDetails", "id": channel_id},
        )
        items = data.get("items", [])
        if not items:
            raise ProviderError(f"YouTube channel not found: {channel_id}")
        return items[0]

    def _get_video_details(self, video_ids: list[str]) -> dict[str, dict]:
        if not video_ids:
            return {}
        data = self._request(
            "videos",
            {"part": "snippet", "id": ",".join(video_ids[:50])},
        )
        return {item["id"]: item["snippet"] for item in data.get("items", [])}

    def _request(self, resource: str, params: dict[str, object]) -> dict:
        query = urlencode({**params, "key": self.api_key})
        request = Request(
            f"{self.BASE_URL}/{resource}?{query}",
            headers={"Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"YouTube API HTTP {exc.code}: {body[:300]}") from exc
        except URLError as exc:
            raise ProviderError(f"YouTube API network error: {exc}") from exc


def _extract_channel_id(value: str) -> str | None:
    if value.startswith("UC") and len(value) >= 20:
        return value
    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "channel":
        return parts[1]
    query_channel = parse_qs(parsed.query).get("channel_id")
    if query_channel:
        return query_channel[0]
    return None


def _extract_handle(value: str) -> str | None:
    if value.startswith("@"):
        return value[1:]
    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    if parts[0].startswith("@"):
        return parts[0][1:]
    if parts[0] in {"c", "user"} and len(parts) >= 2:
        return parts[1]
    return None
