"""Tests for reset_stale_enrichments — startup cleanup of stale async enrichment jobs."""

import pytest

from app.db import init_db, set_db_path
from app.db.repository import create_enrichment_job, get_enrichment_job, reset_stale_enrichments


@pytest.fixture(autouse=True)
async def tmp_db(tmp_path):
    set_db_path(str(tmp_path / "test.db"))
    await init_db()


async def test_reset_pending_to_failed():
    job_id = await create_enrichment_job("AAPL", "screenshot", "https://example.com/chart")
    job = await get_enrichment_job(job_id)
    assert job["status"] == "pending"

    await reset_stale_enrichments()

    job = await get_enrichment_job(job_id)
    assert job["status"] == "failed"
    assert job["error_message"] == "server restarted"


async def test_reset_processing_to_failed():
    from app.db.repository import update_enrichment_job

    job_id = await create_enrichment_job("MSFT", "screenshot", "https://example.com/chart")
    await update_enrichment_job(job_id, "processing")

    await reset_stale_enrichments()

    job = await get_enrichment_job(job_id)
    assert job["status"] == "failed"
    assert job["error_message"] == "server restarted"


async def test_completed_rows_untouched():
    from app.db.repository import update_enrichment_job

    job_id = await create_enrichment_job("GOOGL", "screenshot", "https://example.com/chart")
    await update_enrichment_job(job_id, "completed", enrichment_delta=5.0)

    await reset_stale_enrichments()

    job = await get_enrichment_job(job_id)
    assert job["status"] == "completed"
    assert job["enrichment_delta"] == pytest.approx(5.0)


async def test_no_stale_jobs_no_error():
    """reset_stale_enrichments on empty table completes without error."""
    await reset_stale_enrichments()
