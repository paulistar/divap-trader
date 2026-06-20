"""Fecha posição Tasso quando o bot avisa STOP atingido."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from src.core.config import settings
from src.data.repositories.trade_repo import TradeRepository
from src.execution.binance_broker import BinanceBroker
from src.execution.position_monitor import _pnl_for_buy, _pnl_for_sell, _total_pnl_pct
from src.tasso.models import TassoSignal

logger = logging.getLogger(__name__)

TASSO_PROFILES = ("tasso_curto", "tasso_long")


def _find_open_trade_by_symbol(symbol: str, repo: TradeRepository):
    for trade in repo.list_binance_open_trades():
        if trade.symbol != symbol or trade.status != "open":
            continue
        if trade.profile_id not in TASSO_PROFILES:
            continue
        return trade
    return None


class TassoStopCloser:
    def __init__(
        self,
        trade_repo: TradeRepository | None = None,
        broker: BinanceBroker | None = None,
    ) -> None:
        self._repo = trade_repo or TradeRepository()
        self._broker = broker or BinanceBroker()

    def apply(self, signal: TassoSignal) -> dict:
        if signal.signal_kind != "stop_hit" or not signal.symbol:
            return {"closed": False, "reason": "not_stop_hit"}

        trade = _find_open_trade_by_symbol(signal.symbol, self._repo)
        if trade is None:
            logger.info("Tasso stop hit ignorado — sem posição aberta %s", signal.symbol)
            return {
                "closed": False,
                "reason": "no_open_trade",
                "symbol": signal.symbol,
            }

        if settings.trading_dry_run:
            return {
                "closed": True,
                "reason": "dry_run",
                "trade_id": trade.id,
                "symbol": signal.symbol,
                "profile_id": trade.profile_id,
            }

        close_qty = trade.effective_remaining if trade.has_partial_exits else trade.quantity
        if not close_qty or close_qty <= 0:
            return {"closed": False, "reason": "zero_quantity", "trade_id": trade.id}

        for order_id in (trade.stop_order_id, trade.tp_order_id):
            if order_id and hasattr(self._broker, "cancel_order"):
                try:
                    self._broker.cancel_order(trade.symbol, order_id)
                except Exception as exc:
                    logger.warning("Tasso stop hit: falha cancelar ordem %s: %s", order_id, exc)

        if trade.direction == "buy":
            order = self._broker.market_sell(trade.symbol, close_qty)
        else:
            quote = close_qty * (trade.entry_price or Decimal(0))
            order = self._broker.market_buy_quote(trade.symbol, quote)

        exit_price, _, _ = self._broker.parse_filled(order)
        if exit_price <= 0:
            exit_price = self._broker.fetch_ticker_price(trade.symbol)

        if trade.has_partial_exits and trade.realized_pnl_usdt:
            if trade.direction == "buy":
                chunk_pnl, _ = _pnl_for_buy(trade.entry_price or Decimal(0), exit_price, close_qty)
            else:
                chunk_pnl, _ = _pnl_for_sell(trade.entry_price or Decimal(0), exit_price, close_qty)
            total_pnl = (trade.realized_pnl_usdt or Decimal(0)) + chunk_pnl
            total_pct = _total_pnl_pct(total_pnl, trade.entry_price or Decimal(0), trade.quantity or close_qty)
        elif trade.direction == "buy":
            total_pnl, total_pct = _pnl_for_buy(
                trade.entry_price or Decimal(0), exit_price, close_qty
            )
        else:
            total_pnl, total_pct = _pnl_for_sell(
                trade.entry_price or Decimal(0), exit_price, close_qty
            )

        self._repo.close_trade(
            trade_id=trade.id,
            exit_price=exit_price,
            pnl_usdt=total_pnl,
            pnl_pct=total_pct,
            close_reason="tasso_bot_stop",
            closed_at=datetime.now(UTC),
        )
        logger.info(
            "Tasso trade #%s fechado por STOP do bot %s pnl=%s",
            trade.id,
            signal.symbol,
            total_pnl,
        )
        return {
            "closed": True,
            "reason": "tasso_bot_stop",
            "trade_id": trade.id,
            "symbol": signal.symbol,
            "profile_id": trade.profile_id,
            "exit_price": str(exit_price),
            "pnl_usdt": str(total_pnl),
        }
