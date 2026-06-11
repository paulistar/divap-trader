from decimal import Decimal

from src.data.models.candle import Candle


def _body(candle: Candle) -> Decimal:
    return abs(candle.close - candle.open)


def _range(candle: Candle) -> Decimal:
    return candle.high - candle.low


def _upper_wick(candle: Candle) -> Decimal:
    return candle.high - max(candle.open, candle.close)


def _lower_wick(candle: Candle) -> Decimal:
    return min(candle.open, candle.close) - candle.low


def is_hammer(candle: Candle) -> bool:
    body = _body(candle)
    rng = _range(candle)
    if rng == 0:
        return False
    lower = _lower_wick(candle)
    upper = _upper_wick(candle)
    return (
        lower >= body * 2
        and upper <= body * Decimal("0.5")
        and body / rng <= Decimal("0.35")
    )


def is_shooting_star(candle: Candle) -> bool:
    body = _body(candle)
    rng = _range(candle)
    if rng == 0:
        return False
    upper = _upper_wick(candle)
    lower = _lower_wick(candle)
    return (
        upper >= body * 2
        and lower <= body * Decimal("0.5")
        and body / rng <= Decimal("0.35")
    )


def is_bullish_engulfing(prev: Candle, curr: Candle) -> bool:
    prev_bearish = prev.close < prev.open
    curr_bullish = curr.close > curr.open
    engulfs = curr.open <= prev.close and curr.close >= prev.open
    return prev_bearish and curr_bullish and engulfs


def is_bearish_engulfing(prev: Candle, curr: Candle) -> bool:
    prev_bullish = prev.close > prev.open
    curr_bearish = curr.close < curr.open
    engulfs = curr.open >= prev.close and curr.close <= prev.open
    return prev_bullish and curr_bearish and engulfs


def is_harami(prev: Candle, curr: Candle) -> bool:
    prev_body_high = max(prev.open, prev.close)
    prev_body_low = min(prev.open, prev.close)
    curr_body_high = max(curr.open, curr.close)
    curr_body_low = min(curr.open, curr.close)
    return (
        curr_body_high <= prev_body_high
        and curr_body_low >= prev_body_low
        and _body(curr) < _body(prev)
    )


def detect_reversal_pattern(candles: list[Candle]) -> str | None:
    if len(candles) < 2:
        return None

    prev, curr = candles[-2], candles[-1]

    if is_bullish_engulfing(prev, curr):
        return "bullish_engulfing"
    if is_bearish_engulfing(prev, curr):
        return "bearish_engulfing"
    if is_hammer(curr):
        return "hammer"
    if is_shooting_star(curr):
        return "shooting_star"
    if is_harami(prev, curr):
        return "harami"

    return None
