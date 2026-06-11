from decimal import Decimal

from src.core.constants import FIBO_TARGETS, FIBO_TOLERANCE_PCT
from src.data.models.candle import Candle


def calculate_extension_levels(
    swing_low: Decimal,
    swing_high: Decimal,
    direction: str = "up",
) -> dict[Decimal, Decimal]:
    """Extension levels from swing low → swing high (direction up extends above high)."""
    diff = swing_high - swing_low
    if direction == "up":
        return {ratio: swing_high + diff * ratio for ratio in FIBO_TARGETS}
    return {ratio: swing_low - diff * ratio for ratio in FIBO_TARGETS}


def find_swing_points(
    candles: list[Candle],
    lookback: int = 50,
) -> tuple[Decimal, Decimal] | None:
    """Return (swing_low, swing_high) from recent window."""
    if len(candles) < 3:
        return None

    window = candles[-lookback:] if len(candles) >= lookback else candles
    swing_low = min(c.low for c in window)
    swing_high = max(c.high for c in window)
    return swing_low, swing_high


def find_nearest_extension_level(
    price: Decimal,
    levels: dict[Decimal, Decimal],
    tolerance_pct: Decimal = FIBO_TOLERANCE_PCT,
) -> tuple[Decimal, Decimal] | None:
    for ratio, level_price in levels.items():
        if level_price == 0:
            continue
        distance = abs(price - level_price) / level_price
        if distance <= tolerance_pct:
            return ratio, level_price
    return None


def price_at_extension_target(
    candles: list[Candle],
    lookback: int = 50,
) -> tuple[Decimal, Decimal] | None:
    """Check if current price is near a Fibonacci extension level."""
    swings = find_swing_points(candles, lookback)
    if swings is None:
        return None

    swing_low, swing_high = swings
    current = candles[-1].close

    # Try extension above (bearish reversal zone) and below (bullish context)
    for direction in ("up", "down"):
        levels = calculate_extension_levels(swing_low, swing_high, direction)
        hit = find_nearest_extension_level(current, levels)
        if hit is not None:
            return hit

    return None
