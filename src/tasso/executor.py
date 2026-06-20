"""Executa sinal Tasso na Binance via TradeExecutor."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from src.core.config import settings
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.execution.binance_broker import BinanceBroker
from src.execution.trade_executor import TradeExecutor
from src.profiles.loader import load_profile
from src.tasso.models import TassoSignal

logger = logging.getLogger(__name__)

DEFAULT_STOP_PCT = Decimal("0.02")
DEFAULT_TP_PCT = Decimal("0.03")


def _criteria_stub() -> DIVAPCriteria:
    return DIVAPCriteria(divergence=True, volume=True, fibonacci=True, pattern=True)


def build_divap_signal(signal: TassoSignal, current_price: Decimal) -> DIVAPSignal:
    entry = signal.entry_price or current_price
    stop = signal.stop_loss
    tp = signal.take_profit

    if stop is None:
        if signal.direction == "buy":
            stop = entry * (Decimal("1") - DEFAULT_STOP_PCT)
        else:
            stop = entry * (Decimal("1") + DEFAULT_STOP_PCT)

    if tp is None:
        if signal.direction == "buy":
            tp = entry * (Decimal("1") + DEFAULT_TP_PCT)
        else:
            tp = entry * (Decimal("1") - DEFAULT_TP_PCT)

    return DIVAPSignal(
        symbol=signal.symbol or "BTCUSDT",
        timeframe=signal.timeframe,
        direction=signal.direction or "buy",
        confidence="high",
        criteria=_criteria_stub(),
        entry_price=entry,
        stop_loss=stop,
        targets=signal.take_profit_levels or (tp,),
        current_price=current_price,
        rsi_value=50.0,
        volume_ratio=1.0,
        divergence_type="tasso_external",
        pattern_detected="financial_move_bot",
        fibo_level=None,
        timestamp=datetime.now(UTC),
    )


class TassoExecutor:
    def try_execute(self, signal: TassoSignal) -> dict:
        profile = load_profile(signal.profile_id)
        if profile is None:
            return {"executed": False, "reason": "profile_not_found", "profile_id": signal.profile_id}

        if not settings.trading_enabled:
            return {"executed": False, "reason": "trading_disabled", "profile_id": signal.profile_id}

        if settings.trading_dry_run:
            logger.info(
                "Tasso dry-run %s %s %s",
                signal.profile_id,
                signal.symbol,
                signal.direction,
            )
            return {
                "executed": False,
                "reason": "dry_run",
                "profile_id": signal.profile_id,
                "symbol": signal.symbol,
                "direction": signal.direction,
            }

        from src.data.sources.binance import to_ccxt_symbol

        broker = BinanceBroker()
        try:
            ccxt_sym = to_ccxt_symbol(signal.symbol or "BTCUSDT")
            ticker = broker.exchange.fetch_ticker(ccxt_sym)
            current = Decimal(str(ticker.get("last") or ticker.get("close") or 0))
        except Exception as exc:
            logger.exception("Tasso: falha ao obter preço %s: %s", signal.symbol, exc)
            return {"executed": False, "reason": "price_fetch_failed", "symbol": signal.symbol}

        if current <= 0:
            return {"executed": False, "reason": "invalid_price", "symbol": signal.symbol}

        divap = build_divap_signal(signal, current)
        tp_levels = signal.take_profit_levels
        result = TradeExecutor(broker=broker).try_execute(
            divap,
            alert_id=None,
            market_context=None,
            profile_id=signal.profile_id,
            take_profit_levels=tp_levels,
        )

        return {
            "executed": result.executed,
            "reason": result.reason,
            "trade_id": result.trade_id,
            "profile_id": signal.profile_id,
            "symbol": result.symbol,
            "direction": result.direction,
        }
