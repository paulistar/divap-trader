from __future__ import annotations

import logging

from src.tasso.executor import TassoExecutor
from src.tasso.models import TassoSignal
from src.tasso.trade_close import TassoStopCloser
from src.tasso.trade_update import TassoTradeUpdater

logger = logging.getLogger(__name__)


def dispatch_tasso_signal(signal: TassoSignal) -> dict:
    logger.info(
        "Tasso dispatch kind=%s profile=%s symbol=%s direction=%s stop=%s tps=%s",
        signal.signal_kind,
        signal.profile_id,
        signal.symbol,
        signal.direction,
        signal.stop_loss,
        signal.take_profit_levels,
    )
    if signal.signal_kind == "stop_hit":
        return TassoStopCloser().apply(signal)
    if signal.signal_kind == "update":
        return TassoTradeUpdater().apply(signal)
    return TassoExecutor().try_execute(signal)
