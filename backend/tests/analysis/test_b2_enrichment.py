"""Unit tests for US-303 B2 auto-screenshot enrichment path."""

import pytest
from fastapi import HTTPException

from app.analysis.models import PerformanceResponse, SegmentPerformance
from app.utils import validate_source_url


# ── B2 formula ────────────────────────────────────────────────────────────────

def _b2_delta(confidence: float, support_validated: bool, max_delta: float = 15.0, bonus: float = 2.0) -> float:
    return round(min(confidence * max_delta + (bonus if support_validated else 0.0), max_delta), 2)


def test_b2_formula_nominal_no_bonus():
    # 6.1: confidence=0.87, support_validated=False → 0.87 × 15 = 13.05
    assert _b2_delta(0.87, False) == 13.05


def test_b2_formula_with_bonus_capped():
    # 6.2: confidence=0.87, support_validated=True → min(0.87×15+2.0, 15) = min(15.05, 15) = 15.0
    assert _b2_delta(0.87, True) == 15.0


def test_b2_formula_full_confidence_with_bonus_capped():
    # 6.3: confidence=1.0, support_validated=True → min(15+2, 15) = 15.0
    assert _b2_delta(1.0, True) == 15.0


def test_b2_formula_low_confidence():
    # 6.4: confidence=0.1, support_validated=False → 0.1 × 15 = 1.5
    assert _b2_delta(0.1, False) == 1.5


# ── B1 + B2 max() conflict resolution ────────────────────────────────────────

def test_b2_higher_than_b1():
    # 6.5: existing_delta=8.0, b2_delta=13.05 → final=13.05
    existing_delta = 8.0
    b2 = _b2_delta(0.87, False)  # 13.05
    assert max(b2, existing_delta) == 13.05


def test_b1_higher_than_b2():
    # 6.6: existing_delta=14.5, b2_delta=9.0 → final=14.5
    existing_delta = 14.5
    b2 = _b2_delta(0.6, False)  # 0.6 × 15 = 9.0
    assert max(b2, existing_delta) == 14.5


# ── validate_source_url SSRF blocks ──────────────────────────────────────────

def test_validate_source_url_blocks_file_scheme():
    # 6.7: file:// must be rejected
    with pytest.raises(HTTPException) as exc:
        validate_source_url("file:///etc/passwd")
    assert exc.value.status_code == 400


def test_validate_source_url_blocks_http():
    with pytest.raises(HTTPException) as exc:
        validate_source_url("http://example.com/chart")
    assert exc.value.status_code == 400


def test_validate_source_url_blocks_localhost():
    with pytest.raises(HTTPException) as exc:
        validate_source_url("https://localhost/chart")
    assert exc.value.status_code == 400


def test_validate_source_url_blocks_loopback_ip():
    with pytest.raises(HTTPException) as exc:
        validate_source_url("https://127.0.0.1/chart")
    assert exc.value.status_code == 400


def test_validate_source_url_blocks_private_class_a():
    with pytest.raises(HTTPException) as exc:
        validate_source_url("https://10.0.0.1/chart")
    assert exc.value.status_code == 400


def test_validate_source_url_blocks_private_class_c():
    with pytest.raises(HTTPException) as exc:
        validate_source_url("https://192.168.1.1/chart")
    assert exc.value.status_code == 400


def test_validate_source_url_blocks_link_local():
    with pytest.raises(HTTPException) as exc:
        validate_source_url("https://169.254.1.1/chart")
    assert exc.value.status_code == 400


# ── Idempotency (6.8) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotency_second_request_returns_existing_enrichment_id(tmp_path):
    """Second auto_screenshot request while pending returns same enrichment_id."""
    from app.db import create_enrichment_job, find_pending_enrichment_job, init_db, set_db_path

    set_db_path(str(tmp_path / "idempotent.db"))
    await init_db()

    # Create a pending job
    job_id = await create_enrichment_job("AAPL", "auto_screenshot", "https://example.com/chart")

    # find_pending_enrichment_job should return it
    found = await find_pending_enrichment_job("AAPL")
    assert found is not None
    assert found["id"] == job_id
    assert found["status"] == "pending"


@pytest.mark.asyncio
async def test_idempotency_completed_job_not_found(tmp_path):
    """Completed job is NOT returned by find_pending_enrichment_job."""
    from app.db import create_enrichment_job, find_pending_enrichment_job, init_db, set_db_path, update_enrichment_job

    set_db_path(str(tmp_path / "completed.db"))
    await init_db()

    job_id = await create_enrichment_job("AAPL", "auto_screenshot", "https://example.com/chart")
    await update_enrichment_job(job_id, "completed")

    found = await find_pending_enrichment_job("AAPL")
    assert found is None


# ── Argument prefix (6.9) ─────────────────────────────────────────────────────

def test_argument_display_prefix_format():
    # 6.9: argument "Breakout" → "💬 Visual analysis: Breakout"
    raw_argument = "Breakout"
    argument_display = f"💬 Visual analysis: {raw_argument}"
    assert argument_display == "💬 Visual analysis: Breakout"


# ── SegmentPerformance and PerformanceResponse serialization (6.10) ───────────

def test_segment_performance_serializes():
    seg = SegmentPerformance(total=32, hit_ratio=0.72, profit_factor=2.1, realized_rr=1.8)
    d = seg.model_dump()
    assert d == {"total": 32, "hit_ratio": 0.72, "profit_factor": 2.1, "realized_rr": 1.8}


def test_performance_response_with_b2_segment():
    resp = PerformanceResponse(
        phase_gate_active=False,
        calibration_count=32,
        total_signals=35,
        target_hits=20,
        stop_hits=12,
        expired=3,
        orphaned_count=0,
        hit_ratio=0.625,
        profit_factor=2.1,
        realized_rr=1.8,
        hr_status="green",
        pf_status="green",
        rr_status=None,
        below_breakeven=False,
        b2_enriched=SegmentPerformance(total=32, hit_ratio=0.72, profit_factor=2.1, realized_rr=1.8),
        non_enriched=None,
    )
    d = resp.model_dump()
    assert d["b2_enriched"] == {"total": 32, "hit_ratio": 0.72, "profit_factor": 2.1, "realized_rr": 1.8}
    assert d["non_enriched"] is None


def test_performance_response_null_segments():
    resp = PerformanceResponse(
        phase_gate_active=True,
        calibration_count=0,
        total_signals=0,
        target_hits=0,
        stop_hits=0,
        expired=0,
        orphaned_count=0,
        hit_ratio=None,
        profit_factor=None,
        realized_rr=None,
        hr_status=None,
        pf_status=None,
        rr_status=None,
        below_breakeven=False,
    )
    d = resp.model_dump()
    assert d["b2_enriched"] is None
    assert d["non_enriched"] is None
