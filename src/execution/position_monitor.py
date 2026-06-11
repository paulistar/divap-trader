import logging
from datetime import UTC, datetime
from decimal import Decimal

from src.alerts.telegram import TelegramNotifier
from src.alerts.trade_formatter import format_trade_closed
from src.core.exceptions import ExchangeError
from src.data.repositories.trade_repo import TradeRecord, TradeRepository
from src.data.sources.binance import BinanceSource
from src.execution.binance_broker import BinanceBroker
from src.profiles.exit_policy import should_time_stop
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


class PositionMonitor:
    def __init__(
        self,
        broker: BinanceBroker | None = None,
        trade_repo: TradeRepository | None = None,
        notifier: TelegramNotifier | None = None,
        market_source: BinanceSource | None = None,
    ) -> None:
        self._broker = broker or BinanceBroker()
        self._repo = trade_repo or TradeRepository()
        self._notifier = notifier or TelegramNotifier()
        self._source = market_source or BinanceSource()

    def sync_open_positions(self) -> dict[str, int]:
        trades = self._repo.list_open_trades()
        closed = 0
        errors = 0

        for trade in trades:
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
        if not trade.quantity or trade.quantity <= 0:
            return False
        if trade.direction == "buy":
            order = self._broker.market_sell(trade.symbol, trade.quantity)
        else:
            quote = trade.quantity * (trade.entry_price or Decimal(0))
            order = self._broker.market_buy_quote(trade.symbol, quote)
        exit_price, _, _ = self._broker.parse_filled(order)
        if exit_price <= 0:
            exit_price = self._broker.fetch_ticker_price(trade.symbol)
        return self._close(trade, exit_price, reason)

    def _close(self, trade: TradeRecord, exit_price: Decimal, reason: str) -> bool:
        if not trade.entry_price or not trade.quantity:
            return False

        if trade.direction == "buy":
            pnl, pct = _pnl_for_buy(trade.entry_price, exit_price, trade.quantity)
        else:
            pnl, pct = _pnl_for_sell(trade.entry_price, exit_price, trade.quantity)

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
