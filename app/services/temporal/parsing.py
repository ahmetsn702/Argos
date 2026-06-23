"""Temporal parsing utilities: date parsing and timezone helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y-%m-%dT%H:%M:%S",
)


def parse_temporal(value: Any) -> Optional[datetime]:
    """Parse a date/datetime value into a naive UTC datetime. Returns None on failure."""
    if value is None:
        return None
    if isinstance(value, datetime):
        d = value
    else:
        s = str(value).strip()
        if not s:
            return None
        d = None
        try:
            iso = s[:-1] + "+00:00" if s.endswith("Z") else s
            d = datetime.fromisoformat(iso)
        except ValueError:
            pass
        if d is None:
            for fmt in _DATE_FORMATS:
                try:
                    d = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
        if d is None:
            return None
    if d.tzinfo is not None:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


def to_local(dt: datetime, offset_hours: int) -> datetime:
    """Shift a naive UTC datetime by offset_hours to produce a naive local datetime."""
    return dt + timedelta(hours=offset_hours)


def is_night(dt: datetime, offset_hours: int, start: int, end: int) -> bool:
    """Return True if the local hour (UTC + offset_hours) falls in [start, end)."""
    local = to_local(dt, offset_hours)
    return start <= local.hour < end
