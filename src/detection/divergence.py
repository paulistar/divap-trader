from dataclasses import dataclass
from decimal import Decimal

from src.core.constants import DIVERGENCE_LOOKBACK
from src.data.models.candle import Candle


@dataclass(frozen=True, slots=True)
class DivergenceResult:
    divergence_type: str  # "bullish" | "bearish"
    price_pivot_1: Decimal
    price_pivot_2: Decimal
    rsi_pivot_1: float
    rsi_pivot_2: float
    pivot_index_1: int
    pivot_index_2: int


def _find_swing_low_indices(lows: list[float], min_distance: int = 3) -> list[int]:
    indices: list[int] = []
    for i in range(1, len(lows) - 1):
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            if not indices or i - indices[-1] >= min_distance:
                indices.append(i)
    return indices


def _find_swing_high_indices(highs: list[float], min_distance: int = 3) -> list[int]:
    indices: list[int] = []
    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            if not indices or i - indices[-1] >= min_distance:
                indices.append(i)
    return indices


def detect_divergence(
    candles: list[Candle],
    rsi_values: list[float | None],
    lookback: int = DIVERGENCE_LOOKBACK,
) -> DivergenceResult | None:
    if len(candles) < lookback or len(rsi_values) != len(candles):
        return None

    window_candles = candles[-lookback:]
    window_rsi = rsi_values[-lookback:]
    offset = len(candles) - lookback

    lows = [float(c.low) for c in window_candles]
    highs = [float(c.high) for c in window_candles]

    bullish = _detect_bullish(lows, window_rsi, offset)
    if bullish is not None:
        return bullish

    return _detect_bearish(highs, window_rsi, offset)


def _detect_bullish(
    lows: list[float],
    rsi_values: list[float | None],
    offset: int,
) -> DivergenceResult | None:
    swing_lows = _find_swing_low_indices(lows)
    if len(swing_lows) < 2:
        return None

    i1, i2 = swing_lows[-2], swing_lows[-1]
    if rsi_values[i1] is None or rsi_values[i2] is None:
        return None

    price_1, price_2 = Decimal(str(lows[i1])), Decimal(str(lows[i2]))
    rsi_1, rsi_2 = rsi_values[i1], rsi_values[i2]

    if price_2 < price_1 and rsi_2 > rsi_1:
        return DivergenceResult(
            divergence_type="bullish",
            price_pivot_1=price_1,
            price_pivot_2=price_2,
            rsi_pivot_1=rsi_1,
            rsi_pivot_2=rsi_2,
            pivot_index_1=offset + i1,
            pivot_index_2=offset + i2,
        )
    return None


def _detect_bearish(
    highs: list[float],
    rsi_values: list[float | None],
    offset: int,
) -> DivergenceResult | None:
    swing_highs = _find_swing_high_indices(highs)
    if len(swing_highs) < 2:
        return None

    i1, i2 = swing_highs[-2], swing_highs[-1]
    if rsi_values[i1] is None or rsi_values[i2] is None:
        return None

    price_1, price_2 = Decimal(str(highs[i1])), Decimal(str(highs[i2]))
    rsi_1, rsi_2 = rsi_values[i1], rsi_values[i2]

    if price_2 > price_1 and rsi_2 < rsi_1:
        return DivergenceResult(
            divergence_type="bearish",
            price_pivot_1=price_1,
            price_pivot_2=price_2,
            rsi_pivot_1=rsi_1,
            rsi_pivot_2=rsi_2,
            pivot_index_1=offset + i1,
            pivot_index_2=offset + i2,
        )
    return None
