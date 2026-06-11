from decimal import Decimal

from src.core.constants import VOLUME_MA_PERIOD
from src.data.models.candle import Candle


def volume_ratio(current: Decimal, average: Decimal) -> float:
    if average == 0:
        return 0.0
    return float(current / average)


def compute_volume_ma(
    candles: list[Candle],
    period: int = VOLUME_MA_PERIOD,
) -> Decimal | None:
    if len(candles) < period:
        return None

    window = candles[-period:]
    total = sum(c.volume for c in window)
    return total / Decimal(period)


def is_volume_above_average(
    candles: list[Candle],
    period: int = VOLUME_MA_PERIOD,
) -> bool:
    if len(candles) < period + 1:
        return False

    average = compute_volume_ma(candles[:-1], period)
    if average is None or average == 0:
        return False

    return candles[-1].volume > average
