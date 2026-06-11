from decimal import Decimal

from src.detection.divap_scanner import (
    DIVAPCriteria,
    calculate_stop_loss,
    direction_from_divergence,
    pattern_aligns_with_direction,
    resolve_confidence,
)
from src.detection.divergence import DivergenceResult


def test_resolve_confidence_requires_divergence() -> None:
    criteria = DIVAPCriteria(
        divergence=False, volume=True, fibonacci=True, pattern=True
    )
    assert resolve_confidence(criteria) is None


def test_resolve_confidence_two_confluences_no_alert() -> None:
    criteria = DIVAPCriteria(
        divergence=True, volume=True, fibonacci=False, pattern=False
    )
    assert resolve_confidence(criteria) is None


def test_resolve_confidence_three_is_medium() -> None:
    criteria = DIVAPCriteria(
        divergence=True, volume=True, fibonacci=True, pattern=False
    )
    assert resolve_confidence(criteria) == "medium"


def test_resolve_confidence_four_is_high() -> None:
    criteria = DIVAPCriteria(
        divergence=True, volume=True, fibonacci=True, pattern=True
    )
    assert resolve_confidence(criteria) == "high"


def test_direction_from_bullish_divergence() -> None:
    div = DivergenceResult(
        divergence_type="bullish",
        price_pivot_1=Decimal("100"),
        price_pivot_2=Decimal("90"),
        rsi_pivot_1=25.0,
        rsi_pivot_2=30.0,
        pivot_index_1=5,
        pivot_index_2=15,
    )
    assert direction_from_divergence(div) == "buy"


def test_pattern_alignment() -> None:
    assert pattern_aligns_with_direction("hammer", "buy") is True
    assert pattern_aligns_with_direction("shooting_star", "buy") is False
    assert pattern_aligns_with_direction("bearish_engulfing", "sell") is True


def test_calculate_stop_loss_buy() -> None:
    from datetime import UTC, datetime

    from src.data.models.candle import Candle

    candles = [
        Candle(
            symbol="BTCUSDT",
            timeframe="1h",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=Decimal("100"),
        )
    ]
    stop = calculate_stop_loss("buy", candles, "BTCUSDT")
    assert stop < Decimal("95")
