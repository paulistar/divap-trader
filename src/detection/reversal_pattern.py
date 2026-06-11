from src.data.models.candle import Candle
from src.indicators.patterns import detect_reversal_pattern


def check_reversal_pattern(candles: list[Candle]) -> str | None:
    """P — padrão candlestick de reversão."""
    return detect_reversal_pattern(candles)
