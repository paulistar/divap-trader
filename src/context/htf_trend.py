import logging

from src.context.models import TrendBias
from src.core.exceptions import ExchangeError
from src.data.models.candle import Candle
from src.data.sources.binance import BinanceSource
from src.data.sources.binance_exchange import build_binance_public_exchange

logger = logging.getLogger(__name__)

HTF_TIMEFRAMES: tuple[str, ...] = ("1d", "1w")
HTF_CANDLE_LIMIT = 60
MIN_CANDLES_FULL = 20
MIN_CANDLES_FALLBACK = 5


def classify_trend_from_candles(candles: list[Candle]) -> TrendBias:
    """HTF bias: preço vs SMA longa + inclinação da SMA curta."""
    if len(candles) < MIN_CANDLES_FALLBACK:
        return "unknown"

    closes = [float(c.close) for c in candles]
    long_window = min(len(closes), MIN_CANDLES_FULL)
    short_window = min(5, len(closes))
    sma_long = sum(closes[-long_window:]) / long_window
    sma_short = sum(closes[-short_window:]) / short_window
    current = closes[-1]

    if current > sma_long and sma_short >= sma_long:
        return "bullish"
    if current < sma_long and sma_short <= sma_long:
        return "bearish"
    return "sideways"


def fetch_htf_trends(
    symbol: str,
    source: BinanceSource | None = None,
    limit: int = HTF_CANDLE_LIMIT,
) -> dict[str, TrendBias]:
    """
    Tendência diária e semanal do ativo.

    Usa API pública de produção (sem testnet): sandbox tem poucos candles
    em 1d/1w e classificação falhava como unknown.
    """
    market_source = source or BinanceSource(exchange=build_binance_public_exchange())
    trends: dict[str, TrendBias] = {}

    for timeframe in HTF_TIMEFRAMES:
        try:
            candles = market_source.fetch_ohlcv(symbol, timeframe, limit=limit)
            trend = classify_trend_from_candles(candles)
            if trend == "unknown" and len(candles) < MIN_CANDLES_FULL:
                logger.warning(
                    "HTF %s %s: only %s candles (need %s for full bias)",
                    symbol,
                    timeframe,
                    len(candles),
                    MIN_CANDLES_FULL,
                )
            trends[timeframe] = trend
        except ExchangeError as exc:
            logger.warning("HTF trend failed %s %s: %s", symbol, timeframe, exc)
            trends[timeframe] = "unknown"

    return trends
