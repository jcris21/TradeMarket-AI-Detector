"""Tests for filter_by_proximity — discard S/R levels far from current price."""

from app.analysis.models import ExtractedLevel, filter_by_proximity


def _level(price: float, level_type: str = "support") -> ExtractedLevel:
    return ExtractedLevel(type=level_type, price=price, confidence=0.8)


def test_level_within_threshold_retained():
    # 2.5% away (200 * 0.025 = 5) — should be retained
    levels = [_level(195.0)]
    result = filter_by_proximity(levels, current_price=200.0)
    assert len(result) == 1
    assert result[0].price == 195.0


def test_level_at_exact_boundary_retained():
    # 15.0% exactly — inclusive boundary, should be retained
    levels = [_level(170.0)]
    result = filter_by_proximity(levels, current_price=200.0)
    assert len(result) == 1


def test_level_beyond_threshold_discarded():
    # 15.5% away — should be discarded
    levels = [_level(169.0)]
    result = filter_by_proximity(levels, current_price=200.0)
    assert result == []


def test_empty_list_returns_empty():
    assert filter_by_proximity([], current_price=200.0) == []


def test_mixed_levels_filtered_correctly():
    levels = [_level(195.0), _level(169.0), _level(200.0)]
    result = filter_by_proximity(levels, current_price=200.0)
    assert len(result) == 2
    prices = {lv.price for lv in result}
    assert 195.0 in prices
    assert 200.0 in prices
    assert 169.0 not in prices
