"""Unit tests for compute_freshness() in repository.py."""

from datetime import datetime, timedelta, timezone

import pytest

from app.db.repository import compute_freshness


@pytest.mark.parametrize(
    "hours_ago,expected_status",
    [
        (0.5, "fresh"),
        (1.5, "fresh"),
        (2.0, "active"),   # boundary: exactly 2h → active
        (3.0, "active"),
        (5.0, "aged"),     # boundary: exactly 5h → aged
        (7.0, "aged"),
        (24.0, "expired"),  # boundary: exactly 24h → expired
        (30.0, "expired"),
    ],
)
def test_compute_freshness_status(hours_ago: float, expected_status: str) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    result = compute_freshness(ts)
    assert result["freshness_status"] == expected_status
    assert abs(result["freshness_age_hours"] - hours_ago) < 0.05


def test_compute_freshness_returns_rounded_age() -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=1.23456)).isoformat()
    result = compute_freshness(ts)
    assert isinstance(result["freshness_age_hours"], float)
    # rounded to 2 decimal places
    assert result["freshness_age_hours"] == round(result["freshness_age_hours"], 2)


def test_compute_freshness_accepts_z_suffix() -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = compute_freshness(ts)
    assert result["freshness_status"] == "fresh"
