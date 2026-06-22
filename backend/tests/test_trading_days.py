"""Tests for trading_days_from_now TTL utility."""

from datetime import datetime, timezone
from unittest.mock import patch

from app.utils import trading_days_from_now

# Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6

_MONDAY = datetime(2024, 6, 3, 12, 0, 0, tzinfo=timezone.utc)   # Monday
_FRIDAY = datetime(2024, 6, 7, 12, 0, 0, tzinfo=timezone.utc)   # Friday


def test_from_monday_n1_returns_tuesday():
    with patch("app.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _MONDAY
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = trading_days_from_now(1)
    assert result.weekday() == 1  # Tuesday


def test_from_friday_n1_skips_weekend_returns_monday():
    with patch("app.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _FRIDAY
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = trading_days_from_now(1)
    assert result.weekday() == 0  # Monday


def test_from_friday_n5_returns_next_friday():
    with patch("app.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _FRIDAY
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = trading_days_from_now(5)
    assert result.weekday() == 4  # Friday


def test_n0_returns_same_day():
    with patch("app.utils.datetime") as mock_dt:
        mock_dt.now.return_value = _MONDAY
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = trading_days_from_now(0)
    assert result.weekday() == 0  # Monday (unchanged)


def test_result_is_utc():
    result = trading_days_from_now(1)
    assert result.tzinfo is not None
