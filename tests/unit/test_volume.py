from datetime import UTC, datetime
from decimal import Decimal

from src.data.models.candle import Candle
from src.indicators.volume import is_volume_above_average, volume_ratio


def _candle(volume: str, i: int = 0) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, i, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal(volume),
    )


def test_volume_ratio() -> None:
    assert volume_ratio(Decimal("200"), Decimal("100")) == 2.0
    assert volume_ratio(Decimal("50"), Decimal("100")) == 0.5


def test_volume_ratio_zero_average() -> None:
    assert volume_ratio(Decimal("100"), Decimal("0")) == 0.0


def test_is_volume_above_average() -> None:
    base = [_candle("100", i) for i in range(20)]
    high_vol = _candle("250", 20)
    candles = base + [high_vol]
    assert is_volume_above_average(candles, period=20) is True


def test_is_volume_below_average() -> None:
    base = [_candle("100", i) for i in range(20)]
    low_vol = _candle("50", 20)
    candles = base + [low_vol]
    assert is_volume_above_average(candles, period=20) is False
