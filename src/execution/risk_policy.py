"""Minimum risk/reward by timeframe (fallback when profile has no override)."""

from __future__ import annotations

from decimal import Decimal

DEFAULT_MIN_RR_BY_TIMEFRAME: dict[str, Decimal] = {
    "1m": Decimal("1.0"),
    "5m": Decimal("1.0"),
    "15m": Decimal("1.2"),
    "1h": Decimal("1.2"),
    "4h": Decimal("1.5"),
    "1d": Decimal("1.5"),
    "1w": Decimal("2.0"),
}


def effective_min_risk_reward(
    timeframe: str,
    profile_default: Decimal,
    overrides: dict[str, Decimal] | None = None,
) -> Decimal:
    if overrides and timeframe in overrides:
        return overrides[timeframe]
    return DEFAULT_MIN_RR_BY_TIMEFRAME.get(timeframe, profile_default)
