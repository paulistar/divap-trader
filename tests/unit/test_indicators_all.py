from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.data.models.candle import Candle
from src.indicators.all import compute_all_indicators


def _c(close: str, vol: str, i: int) -> Candle:
    c = Decimal(close)
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=i),
        open=c,
        high=c + Decimal("1"),
        low=c - Decimal("1"),
        close=c,
        volume=Decimal(vol),
    )


def test_compute_all_indicators_returns_snapshot() -> None:
    closes = [str(100 + (i % 3)) for i in range(25)]
    candles = [_c(closes[i], "100", i) for i in range(25)]
    snapshot = compute_all_indicators(candles)

    assert snapshot.rsi_current is not None
    assert isinstance(snapshot.volume_above_average, bool)
    assert snapshot.rsi_series is not None
