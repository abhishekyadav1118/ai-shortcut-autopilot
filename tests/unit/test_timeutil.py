"""Unit tests for time formatting, timezone handling, and DST."""

from datetime import UTC, date, datetime

from autopilot.utils.timeutil import calculate_publish_at, format_seconds_to_timestamp


def test_format_seconds_to_timestamp():
    assert format_seconds_to_timestamp(0) == "00:00"
    assert format_seconds_to_timestamp(65) == "01:05"
    assert format_seconds_to_timestamp(3665) == "01:01:05"


def test_calculate_publish_at_dst_summer():
    # During Daylight Saving Time (EDT = UTC-4)
    # 10:00 AM EDT on July 15 is 14:00 UTC
    now_utc = datetime(2026, 7, 15, 6, 0, 0, tzinfo=UTC)
    target_date = date(2026, 7, 15)
    publish_at = calculate_publish_at(
        local_time_str="10:00",
        tz_name="America/New_York",
        target_date=target_date,
        now_utc=now_utc,
    )
    assert publish_at == "2026-07-15T14:00:00Z"


def test_calculate_publish_at_winter():
    # During Standard Time (EST = UTC-5)
    # 10:00 AM EST on January 15 is 15:00 UTC
    now_utc = datetime(2026, 1, 15, 6, 0, 0, tzinfo=UTC)
    target_date = date(2026, 1, 15)
    publish_at = calculate_publish_at(
        local_time_str="10:00",
        tz_name="America/New_York",
        target_date=target_date,
        now_utc=now_utc,
    )
    assert publish_at == "2026-01-15T15:00:00Z"


def test_calculate_publish_at_late_run_fallback():
    # If the run executes after the scheduled hour (e.g. 16:00 UTC when schedule was 14:00 UTC)
    now_utc = datetime(2026, 7, 15, 16, 0, 0, tzinfo=UTC)
    target_date = date(2026, 7, 15)
    publish_at = calculate_publish_at(
        local_time_str="10:00",
        tz_name="America/New_York",
        target_date=target_date,
        now_utc=now_utc,
    )
    # Fallback to now + 15 minutes (16:15 UTC)
    assert publish_at == "2026-07-15T16:15:00Z"
