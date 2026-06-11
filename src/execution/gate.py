from decimal import Decimal

from src.context.models import MarketContext
from src.core.config import Settings, settings
from src.detection.divap_scanner import DIVAPSignal
from src.execution.risk_manager import risk_reward_ratio

MIN_RISK_REWARD = Decimal("2")


def should_execute_trade(
    signal: DIVAPSignal,
    market_context: MarketContext | None,
    cfg: Settings | None = None,
) -> tuple[bool, str]:
    cfg = cfg or settings

    if not cfg.trading_enabled:
        return False, "trading_disabled"

    if cfg.trading_mode == "testnet" and not cfg.binance_use_testnet:
        return False, "testnet_required"

    if cfg.trading_mode == "live" and cfg.binance_use_testnet:
        return False, "live_mode_requires_production_keys"

    min_conf = cfg.trading_min_confidence.lower()
    if min_conf == "high" and signal.confidence != "high":
        return False, "confidence_below_threshold"

    if (
        market_context
        and cfg.trading_block_on_context_reject
        and market_context.context_verdict == "reject"
    ):
        return False, "context_reject"

    if not signal.targets:
        return False, "no_targets"

    rr = risk_reward_ratio(signal.entry_price, signal.stop_loss, signal.targets[0])
    if rr < MIN_RISK_REWARD:
        return False, f"rr_below_minimum_{rr}"

    return True, "ok"
