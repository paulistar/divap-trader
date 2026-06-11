from datetime import UTC, datetime
from decimal import Decimal

from src.data.models.candle import Candle
from src.indicators.rsi import compute_rsi_series


def _candle(close: str, i: int = 0) -> Candle:
    c = Decimal(close)
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, i, tzinfo=UTC),
        open=c,
        high=c + Decimal("1"),
        low=c - Decimal("1"),
        close=c,
        volume=Decimal("100"),
    )


def test_rsi_returns_none_for_insufficient_data() -> None:
    candles = [_candle("100", i) for i in range(5)]
    result = compute_rsi_series(candles, period=14)
    assert len(result) == 5
    assert all(v is None for v in result)


def test_rsi_computes_values_after_warmup() -> None:
    # Alternating up/down to produce RSI in valid range
    closes = [100, 102, 101, 103, 102, 104, 103, 105, 104, 106,
              105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
    candles = [_candle(str(p), i) for i, p in enumerate(closes)]
    result = compute_rsi_series(candles, period=14)

    assert result[-1] is not None
    assert 0 <= result[-1] <= 100
