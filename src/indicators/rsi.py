import pandas as pd
import pandas_ta as ta

from src.core.constants import RSI_PERIOD
from src.data.models.candle import Candle


def compute_rsi_series(
    candles: list[Candle],
    period: int = RSI_PERIOD,
) -> list[float | None]:
    if not candles:
        return []

    if len(candles) < period + 1:
        return [None] * len(candles)

    closes = pd.Series([float(c.close) for c in candles])
    rsi = ta.rsi(closes, length=period)

    if rsi is None:
        return [None] * len(candles)

    return [None if pd.isna(v) else float(v) for v in rsi]
