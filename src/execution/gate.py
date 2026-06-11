from decimal import Decimal

from src.context.models import MarketContext
from src.core.config import Settings, settings
from src.detection.divap_scanner import DIVAPSignal
from src.execution.risk_manager import risk_reward_ratio
from src.profiles.models import ProfileExecution


def should_execute_trade(
    signal: DIVAPSignal,
    market_context: MarketContext | None,
    cfg: Settings | None = None,
    execution: ProfileExecution | None = None,
    *,
    goal_protected: bool = False,
) -> tuple[bool, str]:
    cfg = cfg or settings

    if not cfg.trading_enabled:
        return False, "trading_disabled"

    if cfg.trading_mode == "testnet" and not cfg.binance_use_testnet:
        return False, "testnet_required"

    if cfg.trading_mode == "live" and cfg.binance_use_testnet:
        return False, "live_mode_requires_production_keys"

    profile_exec = execution
    if profile_exec is None:
        from src.bankroll.service import get_active_execution_profile

        _, profile_exec, meta = get_active_execution_profile()
        goal_protected = meta.get("protected_mode", False)

    min_conf = profile_exec.min_confidence.lower()
    if min_conf == "high" and signal.confidence != "high":
        return False, "confidence_below_threshold"

    if min_conf == "medium" and signal.confidence not in ("high", "medium"):
        return False, "confidence_below_threshold"

    if signal.timeframe not in profile_exec.allowed_timeframes:
        return False, "timeframe_not_allowed_for_profile"

    if (
        market_context
        and profile_exec.block_on_reject
        and market_context.context_verdict == "reject"
    ):
        return False, "context_reject"

    if goal_protected:
        if signal.confidence != "high":
            return False, "monthly_goal_protected"
        if market_context and market_context.context_verdict != "confirm":
            return False, "monthly_goal_protected"

    if not signal.targets:
        return False, "no_targets"

    rr = risk_reward_ratio(signal.entry_price, signal.stop_loss, signal.targets[0])
    if rr < profile_exec.min_risk_reward:
        return False, f"rr_below_minimum_{rr}"

    return True, "ok"
