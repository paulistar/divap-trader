"""Enrich trade records for dashboard display."""

from __future__ import annotations

from decimal import Decimal

from src.data.repositories.trade_repo import TradeRecord
from src.profiles.exit_policy import compute_partial_take_profit_levels
from src.profiles.models import PartialTakeProfitLevel

_DEFAULT_PARTIAL_LEVELS = (
    PartialTakeProfitLevel(distance_pct=25),
    PartialTakeProfitLevel(distance_pct=50),
    PartialTakeProfitLevel(distance_pct=100),
)


def _resolve_take_profit_levels(trade: TradeRecord) -> tuple[Decimal, ...]:
    if trade.take_profit_levels:
        return trade.take_profit_levels
    if (
        trade.entry_price is not None
        and trade.take_profit is not None
        and trade.direction in ("buy", "sell")
    ):
        return compute_partial_take_profit_levels(
            trade.entry_price,
            trade.take_profit,
            trade.direction,
            _DEFAULT_PARTIAL_LEVELS,
        )
    return ()


def _partials_hit(trade: TradeRecord) -> tuple[bool, bool, bool]:
    taken = trade.partials_taken
    if trade.status == "closed" and trade.close_reason == "take_profit" and taken == 0:
        taken = 3
    return (taken >= 1, taken >= 2, taken >= 3)


def enrich_trade_for_dashboard(
    trade: TradeRecord,
    live_prices: dict[str, Decimal],
) -> dict:
    levels = _resolve_take_profit_levels(trade)
    hit1, hit2, hit3 = _partials_hit(trade)
    current = live_prices.get(trade.symbol)

    return {
        "current_price": str(current) if current is not None else None,
        "exit_display": str(trade.exit_price) if trade.exit_price is not None else None,
        "target_prices": [str(level) for level in levels],
        "target_hits": [hit1, hit2, hit3],
    }
