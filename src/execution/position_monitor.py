import logging
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from src.alerts.telegram import TelegramNotifier
from src.alerts.trade_formatter import format_trade_closed, format_trade_partial
from src.core.exceptions import ExchangeError
from src.data.repositories.trade_repo import TradeRecord, TradeRepository
from src.data.sources.interfaces import MarketDataSource
from src.execution.interfaces import ExecutionBroker
from src.execution.binance_broker import BinanceBroker  # noqa: F401 — parse_filled on broker instances
from src.markets.factory import get_broker, get_data_source
from src.markets.types import Venue
from src.profiles.exit_policy import partial_close_quantity, should_time_stop
from src.profiles.loader import load_profile

logger = logging.getLogger(__name__)

CLOSED_STATUSES = frozenset({"closed", "canceled", "filled"})


def _pnl_for_buy(
    entry: Decimal, exit_price: Decimal, quantity: Decimal
) -> tuple[Decimal, Decimal]:
    pnl = (exit_price - entry) * quantity
    pct = ((exit_price - entry) / entry * 100) if entry > 0 else Decimal(0)
    return pnl.quantize(Decimal("0.01")), pct.quantize(Decimal("0.0001"))


def _pnl_for_sell(
    entry: Decimal, exit_price: Decimal, quantity: Decimal
) -> tuple[Decimal, Decimal]:
    pnl = (entry - exit_price) * quantity
    pct = ((entry - exit_price) / entry * 100) if entry > 0 else Decimal(0)
    return pnl.quantize(Decimal("0.01")), pct.quantize(Decimal("0.0001"))


def _total_pnl_pct(total_pnl: Decimal, entry: Decimal, quantity: Decimal) -> Decimal:
    if entry <= 0 or quantity <= 0:
        return Decimal(0)
    notional = entry * quantity
    return (total_pnl / notional * 100).quantize(Decimal("0.0001"))


class PositionMonitor:
    def __init__(
        self,
        broker: ExecutionBroker | None = None,
        trade_repo: TradeRepository | None = None,
        notifier: TelegramNotifier | None = None,
        market_source: MarketDataSource | None = None,
        venue: Venue = Venue.BINANCE,
    ) -> None:
        self._venue = venue
        self._broker = broker or get_broker(venue)
        self._repo = trade_repo or TradeRepository()
        self._notifier = notifier or TelegramNotifier()
        self._source = market_source or get_data_source(venue)

    def sync_open_positions(self) -> dict[str, int]:
        trades = self._repo.list_open_trades()
        closed = 0
        errors = 0

        for trade in trades:
            if trade.market != "crypto" or trade.venue != "binance":
                continue
            try:
                if self._sync_trade(trade):
                    closed += 1
            except Exception as exc:
                logger.error("Monitor failed for trade #%s: %s", trade.id, exc)
                errors += 1

        return {"checked": len(trades), "closed": closed, "errors": errors}

    def _sync_trade(self, trade: TradeRecord) -> bool:
        if self._apply_time_stop(trade):
            return True
        if trade.direction == "buy":
            return self._sync_buy_trade(trade)
        return self._sync_sell_trade(trade)

    def _apply_time_stop(self, trade: TradeRecord) -> bool:
        profile = load_profile(trade.profile_id or "divap")
        if profile is None or profile.exit.time_stop_candles <= 0:
            return False
        try:
            candles = self._source.fetch_ohlcv(trade.symbol, trade.timeframe, limit=100)
        except ExchangeError as exc:
            logger.warning("Time stop skipped for trade #%s: %s", trade.id, exc)
            return False
        if not should_time_stop(trade, profile, candles):
            return False
        logger.info("Time stop closing trade #%s %s", trade.id, trade.symbol)
        return self._market_close(trade, "time_stop")

    def _order_closed(self, symbol: str, order_id: str | None) -> tuple[bool, Decimal | None]:
        if not order_id:
            return False, None
        order = self._broker.fetch_order(symbol, order_id)
        status = (order.get("status") or "").lower()
        if status not in CLOSED_STATUSES:
            return False, None
        avg, _, _ = self._broker.parse_filled(order)
        return True, avg if avg > 0 else None

    def _sync_buy_trade(self, trade: TradeRecord) -> bool:
        if trade.has_partial_exits:
            return self._sync_buy_trade_partials(trade)

        if trade.tp_order_id:
            closed, exit_price = self._order_closed(trade.symbol, trade.tp_order_id)
            if closed and exit_price:
                return self._close(trade, exit_price, "take_profit")

        if trade.stop_order_id:
            closed, exit_price = self._order_closed(trade.symbol, trade.stop_order_id)
            if closed and exit_price:
                return self._close(trade, exit_price, "stop_loss")

        if not trade.entry_price or not trade.stop_loss or not trade.take_profit:
            return False

        price = self._broker.fetch_ticker_price(trade.symbol)
        if price <= trade.stop_loss:
            return self._market_close(trade, "stop_loss")
        if price >= trade.take_profit:
            return self._market_close(trade, "take_profit")
        return False

    def _sync_buy_trade_partials(self, trade: TradeRecord) -> bool:
        if trade.stop_order_id:
            closed, exit_price = self._order_closed(trade.symbol, trade.stop_order_id)
            if closed and exit_price:
                return self._close_with_accumulated(trade, exit_price, "stop_loss")

        if (
            not trade.entry_price
            or not trade.stop_loss
            or not trade.take_profit
            or not trade.take_profit_levels
            or not trade.quantity
        ):
            return False

        price = self._broker.fetch_ticker_price(trade.symbol)
        if price <= trade.stop_loss:
            return self._market_close(trade, "stop_loss")

        levels = trade.take_profit_levels
        if trade.partials_taken >= len(levels):
            return False

        target_price = levels[trade.partials_taken]
        if price >= target_price:
            return self._execute_partial_take_profit(trade, price)
        return False

    def _execute_partial_take_profit(self, trade: TradeRecord, price: Decimal) -> bool:
        if not trade.entry_price or not trade.quantity or not trade.take_profit_levels:
            return False

        remaining = trade.effective_remaining
        sell_qty = partial_close_quantity(
            trade.quantity,
            remaining,
            trade.partials_taken,
            len(trade.take_profit_levels),
        )
        if sell_qty <= 0:
            return False

        order = self._broker.market_sell(trade.symbol, sell_qty)
        exit_price, filled_qty, _ = self._broker.parse_filled(order)
        if exit_price <= 0:
            exit_price = price
        if filled_qty <= 0:
            filled_qty = sell_qty

        chunk_pnl, _ = _pnl_for_buy(trade.entry_price, exit_price, filled_qty)
        realized = (trade.realized_pnl_usdt or Decimal(0)) + chunk_pnl
        new_remaining = remaining - filled_qty
        new_partials = trade.partials_taken + 1
        total_levels = len(trade.take_profit_levels)

        if new_partials >= total_levels or new_remaining <= 0:
            total_pct = _total_pnl_pct(realized, trade.entry_price, trade.quantity)
            return self._finalize_close(
                trade,
                exit_price,
                realized,
                total_pct,
                "take_profit",
            )

        self._repo.record_partial_close(
            trade.id,
            new_remaining,
            new_partials,
            realized,
        )
        logger.info(
            "Trade #%s partial TP %s/%s qty=%s pnl=%s",
            trade.id,
            new_partials,
            total_levels,
            filled_qty,
            chunk_pnl,
        )
        if self._notifier.is_configured():
            self._notifier.send(
                format_trade_partial(
                    trade.id,
                    trade.symbol,
                    trade.direction,
                    new_partials,
                    total_levels,
                    exit_price,
                    chunk_pnl,
                    new_remaining,
                )
            )

        profile = load_profile(trade.profile_id or "divap")
        if (
            profile is not None
            and profile.exit.move_stop_to_breakeven_after > 0
            and new_partials == profile.exit.move_stop_to_breakeven_after
        ):
            updated_trade = replace(
                trade,
                remaining_quantity=new_remaining,
                partials_taken=new_partials,
                realized_pnl_usdt=realized,
            )
            self._move_stop_to_breakeven(updated_trade)
        return False

    def _move_stop_to_breakeven(self, trade: TradeRecord) -> None:
        if not trade.entry_price:
            return
        remaining = trade.effective_remaining
        if remaining <= 0:
            return
        if trade.stop_order_id and hasattr(self._broker, "cancel_order"):
            self._broker.cancel_order(trade.symbol, trade.stop_order_id)

        breakeven = trade.entry_price
        new_stop = self._broker.place_stop_loss_limit(
            trade.symbol,
            remaining,
            breakeven,
            breakeven * Decimal("0.995"),
        )
        new_order_id = str(new_stop["id"]) if new_stop else None
        self._repo.update_stop_loss(trade.id, breakeven, new_order_id)
        logger.info("Trade #%s stop moved to breakeven @ %s", trade.id, breakeven)

    def _sync_sell_trade(self, trade: TradeRecord) -> bool:
        if not trade.entry_price or not trade.stop_loss or not trade.take_profit:
            return False

        price = self._broker.fetch_ticker_price(trade.symbol)
        if price >= trade.stop_loss:
            return self._market_close(trade, "stop_loss")
        if price <= trade.take_profit:
            return self._market_close(trade, "take_profit")
        return False

    def _market_close(self, trade: TradeRecord, reason: str) -> bool:
        close_qty = trade.effective_remaining if trade.has_partial_exits else trade.quantity
        if not close_qty or close_qty <= 0:
            return False
        if trade.direction == "buy":
            order = self._broker.market_sell(trade.symbol, close_qty)
        else:
            quote = close_qty * (trade.entry_price or Decimal(0))
            order = self._broker.market_buy_quote(trade.symbol, quote)
        exit_price, _, _ = self._broker.parse_filled(order)
        if exit_price <= 0:
            exit_price = self._broker.fetch_ticker_price(trade.symbol)

        if trade.has_partial_exits and trade.realized_pnl_usdt:
            return self._close_with_accumulated(trade, exit_price, reason, close_qty)

        return self._close(trade, exit_price, reason, close_quantity=close_qty)

    def _close_with_accumulated(
        self,
        trade: TradeRecord,
        exit_price: Decimal,
        reason: str,
        close_quantity: Decimal | None = None,
    ) -> bool:
        qty = close_quantity or trade.effective_remaining
        if not trade.entry_price or qty <= 0:
            return False

        if trade.direction == "buy":
            chunk_pnl, _ = _pnl_for_buy(trade.entry_price, exit_price, qty)
        else:
            chunk_pnl, _ = _pnl_for_sell(trade.entry_price, exit_price, qty)

        total_pnl = (trade.realized_pnl_usdt or Decimal(0)) + chunk_pnl
        total_pct = _total_pnl_pct(
            total_pnl,
            trade.entry_price,
            trade.quantity or qty,
        )
        return self._finalize_close(trade, exit_price, total_pnl, total_pct, reason)

    def _close(
        self,
        trade: TradeRecord,
        exit_price: Decimal,
        reason: str,
        *,
        close_quantity: Decimal | None = None,
    ) -> bool:
        qty = close_quantity or trade.quantity
        if not trade.entry_price or not qty:
            return False

        if trade.direction == "buy":
            pnl, pct = _pnl_for_buy(trade.entry_price, exit_price, qty)
        else:
            pnl, pct = _pnl_for_sell(trade.entry_price, exit_price, qty)

        return self._finalize_close(trade, exit_price, pnl, pct, reason)

    def _finalize_close(
        self,
        trade: TradeRecord,
        exit_price: Decimal,
        pnl: Decimal,
        pct: Decimal,
        reason: str,
    ) -> bool:
        self._repo.close_trade(
            trade_id=trade.id,
            exit_price=exit_price,
            pnl_usdt=pnl,
            pnl_pct=pct,
            close_reason=reason,
            closed_at=datetime.now(UTC),
        )
        logger.info(
            "Trade #%s closed (%s) pnl=%s USDT", trade.id, reason, pnl
        )
        if self._notifier.is_configured():
            self._notifier.send(
                format_trade_closed(
                    trade.id,
                    trade.symbol,
                    trade.direction,
                    exit_price,
                    pnl,
                    pct,
                    reason,
                )
            )
        return True
