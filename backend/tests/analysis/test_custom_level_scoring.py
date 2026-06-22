"""Tests for ScoringAgent._apply_custom_levels — discrete S/R scoring post-pass."""

import pytest

from app.analysis.models import ConfirmedLevel
from app.analysis.scoring_agent import ENRICHMENT_MAX_DELTA, _apply_custom_levels


def _support(price: float) -> ConfirmedLevel:
    return ConfirmedLevel(type="support", price=price)


def _resistance(price: float) -> ConfirmedLevel:
    return ConfirmedLevel(type="resistance", price=price)


def test_one_support_near_entry_scores_four():
    entry = 100.0
    atr = 5.0
    levels = [_support(entry + 0.5 * atr)]  # within 1 ATR
    delta, applied = _apply_custom_levels(entry, 120.0, atr, levels)
    assert delta == pytest.approx(4.0)
    assert applied == 1


def test_one_resistance_near_target_scores_three():
    target = 120.0
    levels = [_resistance(target * 1.01)]  # 1% from target
    delta, applied = _apply_custom_levels(100.0, target, 5.0, levels)
    assert delta == pytest.approx(3.0)
    assert applied == 1


def test_support_too_far_scores_zero():
    entry = 100.0
    atr = 5.0
    levels = [_support(entry + 2 * atr)]  # 2 ATRs away — beyond 1 ATR threshold
    delta, applied = _apply_custom_levels(entry, 120.0, atr, levels)
    assert delta == 0.0
    assert applied == 0


def test_two_levels_both_score():
    entry = 100.0
    atr = 5.0
    target = 120.0
    levels = [_support(entry + 0.5 * atr), _resistance(target * 1.01)]
    delta, applied = _apply_custom_levels(entry, target, atr, levels)
    assert delta == pytest.approx(7.0)
    assert applied == 2


def test_cap_enforcement():
    # Build levels that would score more than ENRICHMENT_MAX_DELTA if uncapped
    entry = 100.0
    atr = 1.0
    target = 120.0
    # Only first 2 are evaluated; still test cap via mock big delta
    levels = [_support(entry), _support(entry + 0.5)]  # both within ATR = 8 pts total
    delta, applied = _apply_custom_levels(entry, target, atr, levels)
    assert delta <= ENRICHMENT_MAX_DELTA
    assert delta == pytest.approx(min(8.0, ENRICHMENT_MAX_DELTA))


def test_empty_levels_returns_zero():
    delta, applied = _apply_custom_levels(100.0, 120.0, 5.0, [])
    assert delta == 0.0
    assert applied == 0


def test_only_first_two_levels_evaluated():
    entry = 100.0
    atr = 5.0
    # 3 levels all scoring, but only first 2 should count
    levels = [_support(entry + 1), _support(entry + 2), _support(entry + 3)]
    delta, applied = _apply_custom_levels(entry, 120.0, atr, levels)
    assert applied == 2
    assert delta == pytest.approx(8.0)
