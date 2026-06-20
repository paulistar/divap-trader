"""Atualiza trades Tasso abertos quando o bot manda revisão."""

from __future__ import annotations

import logging
from decimal import Decimal

from src.core.config import settings
from src.data.repositories.trade_repo import TradeRepository
from src.execution.binance_broker import BinanceBroker
from src.tasso.models import TassoSignal

logger = logging.getLogger(__name__)


def _find_open_trade(signal: TassoSignal, repo: TradeRepository):
    for trade in repo.list_binance_open_trades():
        if trade.profile_id != signal.profile_id:
            continue
        if trade.symbol != signal.symbol:
            continue
        if trade.status != "open":
            continue
        return trade
    return None


class TassoTradeUpdater:
    def __init__(
        self,
        trade_repo: TradeRepository | None = None,
        broker: BinanceBroker | None = None,
    ) -> None:
        self._repo = trade_repo or TradeRepository()
        self._broker = broker or BinanceBroker()

    def apply(self, signal: TassoSignal) -> dict:
        if signal.signal_kind != "update":
            return {"updated": False, "reason": "not_an_update"}

        trade = _find_open_trade(signal, self._repo)
        if trade is None:
            logger.info(
                "Tasso update ignorado — sem posição aberta %s %s",
                signal.profile_id,
                signal.symbol,
            )
            return {
                "updated": False,
                "reason": "no_open_trade",
                "profile_id": signal.profile_id,
                "symbol": signal.symbol,
            }

        if settings.trading_dry_run:
            return {
                "updated": True,
                "reason": "dry_run",
                "trade_id": trade.id,
                "profile_id": signal.profile_id,
                "symbol": signal.symbol,
                "targets_hit_bot": signal.targets_hit,
                "partials_taken_local": trade.partials_taken,
            }

        stop_changed = False
        if signal.stop_loss is not None and signal.stop_loss != trade.stop_loss:
            stop_changed = self._update_stop(trade, signal.stop_loss)

        targets_synced = False
        if signal.targets_hit > trade.partials_taken:
            logger.info(
                "Tasso update %s #%s: bot marcou %s alvo(s), local=%s — "
                "monitor continua vendendo por preço",
                signal.symbol,
                trade.id,
                signal.targets_hit,
                trade.partials_taken,
            )
            targets_synced = True

        return {
            "updated": stop_changed or targets_synced,
            "reason": "stop_updated" if stop_changed else "targets_noted",
            "trade_id": trade.id,
            "profile_id": signal.profile_id,
            "symbol": signal.symbol,
            "stop_changed": stop_changed,
            "targets_hit_bot": signal.targets_hit,
            "partials_taken_local": trade.partials_taken,
        }

    def _update_stop(self, trade, new_stop: Decimal) -> bool:
        remaining = trade.effective_remaining
        if remaining <= 0:
            return False

        if trade.stop_order_id and hasattr(self._broker, "cancel_order"):
            try:
                self._broker.cancel_order(trade.symbol, trade.stop_order_id)
            except Exception as exc:
                logger.warning("Tasso: falha ao cancelar stop #%s: %s", trade.id, exc)

        limit_price = (
            new_stop * Decimal("0.995")
            if trade.direction == "buy"
            else new_stop * Decimal("1.005")
        )
        new_order = self._broker.place_stop_loss_limit(
            trade.symbol,
            remaining,
            new_stop,
            limit_price,
        )
        new_order_id = str(new_order["id"]) if new_order else None
        self._repo.update_stop_loss(trade.id, new_stop, new_order_id)
        logger.info(
            "Tasso trade #%s stop atualizado %s → %s",
            trade.id,
            trade.stop_loss,
            new_stop,
        )
        return True
