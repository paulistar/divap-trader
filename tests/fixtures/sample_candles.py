from datetime import UTC, datetime
from decimal import Decimal

from src.data.models.candle import Candle

SAMPLE_BTC_1H: list[Candle] = [
    Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, h, tzinfo=UTC),
        open=Decimal("42000") + Decimal(h * 10),
        high=Decimal("42100") + Decimal(h * 10),
        low=Decimal("41900") + Decimal(h * 10),
        close=Decimal("42050") + Decimal(h * 10),
        volume=Decimal("100.5") + Decimal(h),
    )
    for h in range(5)
]
