"""Async integration tests for analysis_tickers upgrade-seed logic in init_db()."""

import uuid
from datetime import datetime, timezone

import aiosqlite
import pytest

from app.analysis.seed_tickers import LEGACY_TICKERS, SEED_TICKERS, SEED_VERSION
from app.db.connection import init_db, set_db_path
from app.db.schema import DEFAULT_USER_ID


@pytest.fixture
async def db_path(tmp_path):
    """Temporary DB path wired into connection module; reset after each test."""
    path = str(tmp_path / "test.db")
    set_db_path(path)
    yield path
    set_db_path(str(tmp_path / "unused.db"))


async def _get_analysis_tickers(db_path: str) -> list[dict]:
    """Return all analysis_tickers rows for the default user."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT ticker, sector, sub_sector, seed_version "
            "FROM analysis_tickers WHERE user_id = ?",
            (DEFAULT_USER_ID,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _insert_legacy_tickers(db_path: str) -> None:
    """Seed the legacy 10 tickers (without sector data) to simulate an old install."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS analysis_tickers (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                ticker TEXT NOT NULL,
                added_at TEXT NOT NULL,
                UNIQUE(user_id, ticker)
            );
            """
        )
        for ticker in LEGACY_TICKERS:
            await db.execute(
                "INSERT OR IGNORE INTO analysis_tickers (id, user_id, ticker, added_at) "
                "VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
            )
        await db.commit()


async def _insert_custom_tickers(db_path: str, extra: list[str]) -> None:
    """Seed legacy tickers PLUS custom tickers to simulate a modified install."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS analysis_tickers (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                ticker TEXT NOT NULL,
                added_at TEXT NOT NULL,
                UNIQUE(user_id, ticker)
            );
            """
        )
        all_tickers = list(LEGACY_TICKERS) + extra
        for ticker in all_tickers:
            await db.execute(
                "INSERT OR IGNORE INTO analysis_tickers (id, user_id, ticker, added_at) "
                "VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
            )
        await db.commit()


async def test_fresh_install_seeds_100_rows(db_path: str) -> None:
    """Empty analysis_tickers → init_db() inserts all 100 seed tickers."""
    await init_db()

    rows = await _get_analysis_tickers(db_path)
    assert len(rows) == 100, f"Expected 100 rows, got {len(rows)}"


async def test_fresh_install_rows_have_sector_and_seed_version(db_path: str) -> None:
    """All rows inserted on fresh install must have sector, sub_sector, seed_version."""
    await init_db()

    rows = await _get_analysis_tickers(db_path)
    for row in rows:
        assert row["sector"], f"Missing sector for {row['ticker']}"
        assert row["sub_sector"], f"Missing sub_sector for {row['ticker']}"
        assert row["seed_version"] == SEED_VERSION, f"Wrong seed_version for {row['ticker']}"


async def test_legacy_upgrade_replaces_10_with_100(db_path: str) -> None:
    """Legacy 10-ticker install is truncated and replaced with 100 tickers."""
    await _insert_legacy_tickers(db_path)

    await init_db()

    rows = await _get_analysis_tickers(db_path)
    tickers = {r["ticker"] for r in rows}
    assert len(rows) == 100
    assert LEGACY_TICKERS.issubset(tickers)


async def test_legacy_upgrade_stamps_seed_version(db_path: str) -> None:
    """All rows after legacy upgrade must carry SEED_VERSION."""
    await _insert_legacy_tickers(db_path)
    await init_db()

    rows = await _get_analysis_tickers(db_path)
    for row in rows:
        assert row["seed_version"] == SEED_VERSION, f"Missing seed_version for {row['ticker']}"


async def test_additive_merge_preserves_custom_tickers(db_path: str) -> None:
    """Custom tickers beyond the legacy set are never deleted."""
    custom = ["CUSTOM_XYZ"]
    await _insert_custom_tickers(db_path, custom)

    await init_db()

    rows = await _get_analysis_tickers(db_path)
    tickers = {r["ticker"] for r in rows}
    assert "CUSTOM_XYZ" in tickers, "Custom ticker was deleted during additive merge"


async def test_additive_merge_adds_missing_seed_tickers(db_path: str) -> None:
    """Additive merge still inserts the 100 seed tickers (excluding what's already there)."""
    custom = ["CUSTOM_XYZ"]
    await _insert_custom_tickers(db_path, custom)

    await init_db()

    rows = await _get_analysis_tickers(db_path)
    seed_set = {e["ticker"] for e in SEED_TICKERS}
    present = {r["ticker"] for r in rows}
    assert seed_set.issubset(present), "Some seed tickers are missing after additive merge"


async def test_column_migration_is_idempotent(db_path: str) -> None:
    """Running init_db() twice does not raise and does not duplicate rows."""
    await init_db()
    await init_db()

    rows = await _get_analysis_tickers(db_path)
    assert len(rows) == 100


async def test_additive_merge_idempotent_when_all_100_present(db_path: str) -> None:
    """Running init_db() on a DB that already has 100+ tickers does not delete any."""
    custom = ["CUSTOM_XYZ"]
    await _insert_custom_tickers(db_path, custom)
    await init_db()

    count_after_first = len(await _get_analysis_tickers(db_path))

    await init_db()

    rows_after_second = await _get_analysis_tickers(db_path)
    tickers = {r["ticker"] for r in rows_after_second}
    assert "CUSTOM_XYZ" in tickers
    assert len(rows_after_second) == count_after_first
