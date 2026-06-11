import logging
from typing import Literal

from src.context.models import TrendBias
from src.core.exceptions import ExchangeError
from src.data.models.candle import Candle
from src.data.sources.binance import BinanceSource

logger = logging.getLogger(__name__)

TrendBiasType = Literal["bullish", "bearish", "sideways", "unknown"]

HTF_TIMEFRAMES: tuple[str, ...] = ("1d", "1w")


def classify_trend_from_candles(candles: list[Candle]) -> TrendBias:
    """Simple HTF bias: price vs SMA20 + SMA5 slope."""
    if len(candles) < 20:
        return "unknown"

    closes = [float(c.close) for c in candles]
    sma20 = sum(closes[-20:]) / 20
    sma5 = sum(closes[-5:]) / 5
    current = closes[-1]

    if current > sma20 and sma5 >= sma20:
        return "bullish"
    if current < sma20 and sma5 <= sma20:
        return "bearish"
    return "sideways"


def fetch_htf_trends(
    symbol: str,
    source: BinanceSource | None = None,
    limit: int = 60,
) -> dict[str, TrendBias]:
    """Daily and weekly trend for the traded symbol."""
    exchange = source or BinanceSource()
    trends: dict[str, TrendBias] = {}

    for timeframe in HTF_TIMEFRAMES:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            trends[timeframe] = classify_trend_from_candles(candles)
        except ExchangeError as exc:
            logger.warning("HTF trend failed %s %s: %s", symbol, timeframe, exc)
            trends[timeframe] = "unknown"

    return trends
