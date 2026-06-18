from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import BRISBANE_TZ_NAME


BRISBANE_TZ = ZoneInfo(BRISBANE_TZ_NAME)


def brisbane_day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    local_now = now.astimezone(BRISBANE_TZ)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=BRISBANE_TZ)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def is_in_window(value: datetime, start_utc: datetime, end_utc: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value_utc = value.astimezone(timezone.utc)
    return start_utc <= value_utc < end_utc
