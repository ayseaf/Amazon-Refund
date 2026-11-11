from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> str:
    """Fixed-width UTC timestamp. Lexicographic order matches chronological order."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def as_utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
