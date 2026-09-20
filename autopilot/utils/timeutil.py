"""Time and timezone calculation utilities."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def format_seconds_to_timestamp(seconds: float) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    total_seconds = int(max(0, seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def calculate_publish_at(
    local_time_str: str = "10:00",
    tz_name: str = "America/New_York",
    target_date: date | None = None,
    now_utc: datetime | None = None,
) -> str:
    """
    Calculate RFC 3339 UTC timestamp for YouTube publishAt scheduling.

    If the computed publish time is in the past relative to now_utc (late run),
    falls back to now_utc + 15 minutes.
    """
    if now_utc is None:
        now_utc = datetime.now(UTC)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)

    tz = ZoneInfo(tz_name)

    if target_date is None:
        # Determine local date in target timezone
        target_date = now_utc.astimezone(tz).date()

    hour_str, minute_str = local_time_str.split(":")
    target_local_dt = datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=int(hour_str),
        minute=int(minute_str),
        tzinfo=tz,
    )

    target_utc = target_local_dt.astimezone(UTC)

    # Fallback to now + 15 minutes if computed time is less than 5 minutes in the future
    if target_utc <= now_utc + timedelta(minutes=5):
        target_utc = now_utc + timedelta(minutes=15)

    # Format as RFC 3339 string (e.g. 2026-09-20T14:00:00Z)
    return target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
