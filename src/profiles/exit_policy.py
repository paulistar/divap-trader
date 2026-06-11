"""Profile-specific take-profit and time-stop rules."""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal

from src.data.models.candle import Candle
from src.data.repositories.trade_repo import TradeRecord
from src.detection.divap_scanner import DIVAPSignal, Direction
from src.indicators.fibonacci import calculate_extension_levels, find_swing_points
from src.profiles.loader import load_profile
from src.profiles.models import ProfileExit, TradingProfile


def fibo_take_profit_price(
    direction: Direction,
    candles: list[Candle],
    entry_price: Decimal,
    fibo_ratio: Decimal,
) -> Decimal | None:
    swings = find_swing_points(candles)
    if swings is None:
        return None

    swing_low, swing_high = swings
    ext_direction = "up" if direction == "buy" else "down"
    levels = calculate_extension_levels(swing_low, swing_high, ext_direction)
    price = levels.get(fibo_ratio)
    if price is None:
        return None

    if direction == "buy" and price > entry_price:
        return price
    if direction == "sell" and price < entry_price:
        return price
    return None


def resolve_take_profit(
    signal: DIVAPSignal,
    profile: TradingProfile,
    candles: list[Candle] | None = None,
) -> Decimal | None:
    if not signal.targets:
        return None

    fibo_ratio = profile.exit.take_profit_fibo
    if fibo_ratio is None:
        return signal.targets[0]

    if candles is None:
        return signal.targets[0]

    price = fibo_take_profit_price(
        signal.direction,
        candles,
        signal.entry_price,
        fibo_ratio,
    )
    return price if price is not None else signal.targets[0]


def should_time_stop(
    trade: TradeRecord,
    profile: TradingProfile,
    candles: list[Candle],
) -> bool:
    rules = profile.exit
    if rules.time_stop_candles <= 0:
        return False
    if trade.timeframe not in rules.time_stop_timeframes:
        return False
    if trade.entry_price is None or trade.opened_at is None:
        return False

    opened_at = trade.opened_at
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=UTC)
    else:
        opened_at = opened_at.astimezone(UTC)

    candles_after_entry = []
    for candle in candles:
        ts = candle.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        else:
            ts = ts.astimezone(UTC)
        if ts >= opened_at:
            candles_after_entry.append(candle)
    if len(candles_after_entry) < rules.time_stop_candles:
        return False

    current = candles[-1].close
    entry = trade.entry_price
    min_move = rules.time_stop_min_move_pct
    if entry <= 0:
        return False

    if trade.direction == "buy":
        move_pct = (current - entry) / entry
    else:
        move_pct = (entry - current) / entry

    return move_pct < min_move


def exit_rules_for_profile(profile_id: str | None) -> ProfileExit:
    profile = load_profile(profile_id or "divap")
    if profile is None:
        return ProfileExit(
            take_profit_fibo=None,
            time_stop_candles=0,
            time_stop_min_move_pct=Decimal("0"),
            time_stop_timeframes=(),
        )
    return profile.exit
