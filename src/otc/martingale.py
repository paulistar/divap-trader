from __future__ import annotations

from decimal import Decimal

from src.otc.models import OtcMartingale, OtcSignal, OtcTradeResult


def stake_for_level(
    base_stake: Decimal,
    martingale: OtcMartingale,
    protection_level: int,
) -> Decimal:
    if protection_level <= 0:
        return base_stake
    level = min(protection_level, martingale.max_protections)
    multiplier = martingale.multiplier**level
    return (base_stake * multiplier).quantize(Decimal("0.01"))


def max_auto_protections_for_signal(signal: OtcSignal, martingale: OtcMartingale) -> int:
    if signal.max_auto_protections is not None:
        return max(0, signal.max_auto_protections)
    if not martingale.enabled:
        return 0
    return max(0, martingale.max_protections)


def is_loss(result: OtcTradeResult) -> bool:
    return result.pnl_usd is not None and result.pnl_usd < 0


def is_win(result: OtcTradeResult) -> bool:
    return result.pnl_usd is not None and result.pnl_usd > 0


def sequence_reason(legs: tuple[OtcTradeResult, ...], max_protections: int) -> str:
    if not legs:
        return "no_legs"
    last = legs[-1]
    if not last.executed:
        return f"execution_failed:{last.reason}"
    if last.dry_run:
        return "dry_run"
    if any(is_win(leg) for leg in legs):
        return "sequence_win"
    if len(legs) >= max_protections + 1 and all(is_loss(leg) for leg in legs if leg.pnl_usd is not None):
        return "sequence_loss"
    if last.pnl_usd is not None and last.pnl_usd == 0:
        return "sequence_even"
    return "sequence_stopped"
