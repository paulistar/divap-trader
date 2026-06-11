from datetime import UTC, datetime
from decimal import Decimal

from src.data.models.candle import Candle


def test_candle_is_immutable() -> None:
    candle = Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("0.5"),
        close=Decimal("1.5"),
        volume=Decimal("100"),
    )
    assert candle.to_row()[0] == "BTCUSDT"
    assert candle.to_row()[3] == Decimal("1")
