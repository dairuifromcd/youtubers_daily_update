from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import AppSettings, ChannelConfig


class ConfigError(ValueError):
    pass


def load_project_config(path: str | Path) -> tuple[list[ChannelConfig], AppSettings]:
    raw = _load_yaml_like(Path(path))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a mapping.")

    channels_raw = raw.get("channels", [])
    if channels_raw is None:
        channels_raw = []
    if not isinstance(channels_raw, list):
        raise ConfigError("`channels` must be a list.")

    channels = [_parse_channel(item, index) for index, item in enumerate(channels_raw)]
    settings = _parse_settings(raw.get("settings", {}))
    return channels, settings


def _parse_channel(item: Any, index: int) -> ChannelConfig:
    if not isinstance(item, dict):
        raise ConfigError(f"channels[{index}] must be a mapping.")

    name = str(item.get("name", "")).strip()
    channel_id = _optional_str(item.get("channel_id"))
    url = _optional_str(item.get("url"))
    enabled = _as_bool(item.get("enabled", True))

    if not name:
        raise ConfigError(f"channels[{index}].name is required.")
    if enabled and not channel_id and not url:
        raise ConfigError(f"channels[{index}] requires `channel_id` or `url`.")

    return ChannelConfig(name=name, enabled=enabled, channel_id=channel_id, url=url)


def _parse_settings(raw: Any) -> AppSettings:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("`settings` must be a mapping.")

    languages = raw.get("preferred_subtitle_languages", ("zh.*", "en.*"))
    if isinstance(languages, str):
        languages = tuple(part.strip() for part in languages.split(",") if part.strip())
    elif isinstance(languages, list):
        languages = tuple(str(item).strip() for item in languages if str(item).strip())
    else:
        languages = ("zh.*", "en.*")

    return AppSettings(
        state_path=str(raw.get("state_path", "state/seen_videos.sqlite")),
        max_videos_per_channel=int(raw.get("max_videos_per_channel", 10)),
        max_videos_per_run=int(raw.get("max_videos_per_run", 20)),
        max_transcript_chars=int(raw.get("max_transcript_chars", 50000)),
        preferred_subtitle_languages=languages or ("zh.*", "en.*"),
    )


def _load_yaml_like(path: Path) -> Any:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_limited_yaml(text)
    return yaml.safe_load(text)


def _parse_limited_yaml(text: str) -> dict[str, Any]:
    """Small fallback parser for this project's simple channels.yml shape."""
    result: dict[str, Any] = {"channels": []}
    current_section: str | None = None
    current_item: dict[str, Any] | None = None
    current_settings_list_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if not raw_line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1]
            if current_section == "channels":
                result.setdefault("channels", [])
                current_settings_list_key = None
            elif current_section == "settings":
                result.setdefault("settings", {})
                current_settings_list_key = None
            continue

        if current_section == "channels":
            if stripped.startswith("- "):
                current_item = {}
                result["channels"].append(current_item)
                remainder = stripped[2:].strip()
                if remainder:
                    key, value = _split_key_value(remainder)
                    current_item[key] = _coerce_scalar(value)
            elif current_item is not None:
                key, value = _split_key_value(stripped)
                current_item[key] = _coerce_scalar(value)
        elif current_section == "settings":
            settings = result.setdefault("settings", {})
            if stripped.startswith("- ") and current_settings_list_key:
                settings[current_settings_list_key].append(_coerce_scalar(stripped[2:].strip()))
                continue
            key, value = _split_key_value(stripped)
            if value == "":
                settings[key] = []
                current_settings_list_key = key
            else:
                settings[key] = _coerce_scalar(value)
                current_settings_list_key = None
        else:
            key, value = _split_key_value(stripped)
            result[key] = _coerce_scalar(value)

    return result


def _split_key_value(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ConfigError(f"Invalid config line: {line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _coerce_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    try:
        return int(value)
    except ValueError:
        return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() not in {"0", "false", "no", "off"}
