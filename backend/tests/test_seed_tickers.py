"""Offline unit tests for seed_tickers.py — no DB or network required."""

import pytest

from app.analysis.seed_tickers import LEGACY_TICKERS, SEED_TICKERS, SEED_VERSION


def test_seed_tickers_count_is_100() -> None:
    assert len(SEED_TICKERS) == 100


def test_seed_tickers_no_duplicates() -> None:
    tickers = [e["ticker"] for e in SEED_TICKERS]
    assert len(tickers) == len(set(tickers)), "Duplicate tickers found in SEED_TICKERS"


def test_seed_tickers_all_have_required_fields() -> None:
    for entry in SEED_TICKERS:
        assert entry.get("ticker"), f"Missing ticker in entry: {entry}"
        assert entry.get("sector"), f"Missing sector for ticker {entry.get('ticker')}"
        assert entry.get("sub_sector"), f"Missing sub_sector for ticker {entry.get('ticker')}"


def test_legacy_tickers_matches_original_10() -> None:
    expected = frozenset({"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"})
    assert LEGACY_TICKERS == expected


def test_seed_version_is_string() -> None:
    assert isinstance(SEED_VERSION, str)
    assert SEED_VERSION  # non-empty


def test_seed_tickers_contains_legacy_tickers() -> None:
    seed_set = {e["ticker"] for e in SEED_TICKERS}
    assert LEGACY_TICKERS.issubset(seed_set), "LEGACY_TICKERS must be a subset of SEED_TICKERS"


def test_seed_tickers_no_imports_from_db_or_app() -> None:
    """Verify seed_tickers module has no app/db imports (import cycle guard)."""
    import importlib
    import sys

    mod_name = "app.analysis.seed_tickers"
    if mod_name in sys.modules:
        mod = sys.modules[mod_name]
    else:
        mod = importlib.import_module(mod_name)

    source_file = mod.__file__
    assert source_file is not None
    with open(source_file) as f:
        source = f.read()

    forbidden = ["from app.db", "from app.market", "import app.db", "import app.market"]
    for pattern in forbidden:
        assert pattern not in source, f"Import cycle risk: found '{pattern}' in seed_tickers.py"
