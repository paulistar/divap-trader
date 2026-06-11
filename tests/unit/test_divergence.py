from datetime import UTC, datetime
from decimal import Decimal

from src.data.models.candle import Candle
from src.detection.divergence import detect_divergence


def _candle(low: str, high: str, close: str, i: int) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, i, tzinfo=UTC),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("100"),
    )


def test_bullish_divergence() -> None:
    """Price lower low + RSI higher low = bullish divergence."""
    n = 20
    lows = [100.0] * n
    lows[4] = 85.0
    lows[5] = 80.0  # first swing low
    lows[6] = 85.0
    lows[14] = 75.0
    lows[15] = 70.0  # second swing low (lower price)
    lows[16] = 75.0

    candles = [
        _candle(str(lows[i]), str(lows[i] + 5), str(lows[i] + 2), i)
        for i in range(n)
    ]

    rsi: list[float | None] = [50.0] * n
    rsi[5] = 28.0
    rsi[15] = 35.0  # higher RSI at lower price low

    result = detect_divergence(candles, rsi, lookback=20)
    assert result is not None
    assert result.divergence_type == "bullish"
    assert result.price_pivot_2 < result.price_pivot_1
    assert result.rsi_pivot_2 > result.rsi_pivot_1


def test_bearish_divergence() -> None:
    n = 20
    highs = [100.0] * n
    highs[4] = 115.0
    highs[5] = 120.0  # first swing high
    highs[6] = 115.0
    highs[14] = 125.0
    highs[15] = 130.0  # second swing high (higher price)
    highs[16] = 125.0

    candles = [
        _candle(str(highs[i] - 5), str(highs[i]), str(highs[i] - 2), i)
        for i in range(n)
    ]

    rsi: list[float | None] = [50.0] * n
    rsi[5] = 72.0
    rsi[15] = 65.0  # lower RSI at higher price high

    result = detect_divergence(candles, rsi, lookback=20)
    assert result is not None
    assert result.divergence_type == "bearish"


def test_no_divergence_when_insufficient_data() -> None:
    candles = [_candle("100", "101", "100", i) for i in range(5)]
    rsi: list[float | None] = [50.0] * 5
    assert detect_divergence(candles, rsi) is None
