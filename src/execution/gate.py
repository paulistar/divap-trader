from decimal import Decimal

from src.context.models import MarketContext
from src.core.config import Settings, settings
from src.data.models.candle import Candle
from src.detection.divap_scanner import DIVAPSignal
from src.execution.risk_manager import risk_reward_ratio
from src.execution.risk_policy import effective_min_risk_reward
from src.profiles.exit_policy import resolve_take_profit
from src.profiles.models import ProfileExecution, TradingProfile


def should_execute_trade(
    signal: DIVAPSignal,
    market_context: MarketContext | None,
    cfg: Settings | None = None,
    execution: ProfileExecution | None = None,
    *,
    goal_protected: bool = False,
    profile: TradingProfile | None = None,
    candles: list[Candle] | None = None,
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
        from src.bankroll.execution_context import get_active_execution_profile

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

    if profile is not None:
        take_profit = resolve_take_profit(signal, profile, candles)
    else:
        take_profit = signal.targets[0]

    if take_profit is None:
        return False, "no_targets"

    rr = risk_reward_ratio(signal.entry_price, signal.stop_loss, take_profit)
    min_rr = effective_min_risk_reward(
        signal.timeframe,
        profile_exec.min_risk_reward,
        profile_exec.min_risk_reward_by_timeframe,
    )
    if rr < min_rr:
        return False, f"rr_below_minimum_{rr}"

    if profile is not None and profile.id == "anti_divap":
        from src.profiles.contrarian import contrarian_setup_aligned

        aligned, contrarian_reason = contrarian_setup_aligned(signal, market_context)
        if not aligned:
            return False, contrarian_reason

    return True, "ok"
