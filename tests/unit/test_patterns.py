from datetime import UTC, datetime
from decimal import Decimal

from src.data.models.candle import Candle
from src.indicators.patterns import detect_reversal_pattern


def _c(
    o: str,
    h: str,
    l: str,
    cl: str,
    i: int = 0,
) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, i, tzinfo=UTC),
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(cl),
        volume=Decimal("100"),
    )


def test_detect_hammer() -> None:
    # Small body at top, long lower wick, minimal upper wick
    prev = _c("100", "101", "99", "99.5", 0)
    hammer = _c("100", "100.2", "90", "100.2", 1)
    assert detect_reversal_pattern([prev, hammer]) == "hammer"


def test_detect_bullish_engulfing() -> None:
    prev = _c("105", "106", "100", "101", 0)  # bearish
    curr = _c("100", "108", "99", "107", 1)   # bullish engulfing
    assert detect_reversal_pattern([prev, curr]) == "bullish_engulfing"


def test_detect_shooting_star() -> None:
    prev = _c("100", "101", "99", "100", 0)
    star = _c("109", "110.5", "109.1", "109.2", 1)  # long upper wick, small body
    assert detect_reversal_pattern([prev, star]) == "shooting_star"


def test_no_pattern() -> None:
    prev = _c("100", "101", "99", "100.5", 0)
    curr = _c("100.5", "101.5", "100", "101", 1)
    assert detect_reversal_pattern([prev, curr]) is None
