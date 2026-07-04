from datetime import datetime, timezone

from app.domains.mission.policy import local_date_for_timezone


def test_local_date_for_timezone_falls_back_to_default_for_invalid_timezone() -> None:
    now = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)

    assert local_date_for_timezone("not-a-timezone", now=now).isoformat() == "2026-07-02"


def test_local_date_for_timezone_falls_back_to_default_for_empty_timezone() -> None:
    now = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)

    assert local_date_for_timezone("", now=now).isoformat() == "2026-07-02"
