from decimal import Decimal

from src.data.models.candle import Candle
from src.indicators.fibonacci import price_at_extension_target


def check_fibonacci_zone(candles: list[Candle]) -> tuple[Decimal, Decimal] | None:
    """A — preço em alvo de extensão Fibonacci."""
    return price_at_extension_target(candles)
