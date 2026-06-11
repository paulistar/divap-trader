import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from src.context.models import MarketContext
from src.core.config import settings
from src.core.exceptions import ExchangeError
from src.data.repositories.trade_repo import TradeRepository
from src.detection.divap_scanner import DIVAPSignal
from src.execution.binance_broker import BinanceBroker
from src.bankroll.service import get_active_execution_profile
from src.execution.gate import should_execute_trade
from src.execution.risk_manager import (
    MIN_ORDER_USDT,
    base_quantity_from_quote,
    calculate_quote_amount,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TradeExecutionResult:
    trade_id: int | None
    executed: bool
    reason: str
    symbol: str
    direction: str
    quote_amount: Decimal | None = None
    entry_price: Decimal | None = None
    quantity: Decimal | None = None


class TradeExecutor:
    def __init__(
        self,
        broker: BinanceBroker | None = None,
        trade_repo: TradeRepository | None = None,
    ) -> None:
        self._broker = broker or BinanceBroker()
        self._repo = trade_repo or TradeRepository()

    def try_execute(
        self,
        signal: DIVAPSignal,
        alert_id: int,
        market_context: MarketContext | None,
    ) -> TradeExecutionResult:
        _, execution, meta = get_active_execution_profile()
        allowed, reason = should_execute_trade(
            signal,
            market_context,
            settings,
            execution,
            goal_protected=meta.get("protected_mode", False),
        )
        if not allowed:
            logger.info(
                "Trade skipped %s %s: %s", signal.symbol, signal.timeframe, reason
            )
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason=reason,
                symbol=signal.symbol,
                direction=signal.direction,
            )

        if self._repo.count_open_trades() >= execution.max_open_trades:
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="max_open_trades",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        if self._repo.has_open_trade(signal.symbol, signal.timeframe):
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="duplicate_open_trade",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        take_profit = signal.targets[0]

        if settings.trading_dry_run:
            quote = self._resolve_quote_amount(signal)
            trade_id = self._repo.create_trade(
                alert_id=alert_id,
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                confidence=signal.confidence,
                status="simulated",
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=take_profit,
                quantity=base_quantity_from_quote(quote, signal.entry_price),
                quote_amount=quote,
                context_verdict=(
                    market_context.context_verdict if market_context else None
                ),
                context_score=market_context.context_score if market_context else None,
                exchange_order_id=None,
                stop_order_id=None,
                tp_order_id=None,
                trading_mode=settings.trading_mode,
                opened_at=datetime.now(UTC),
            )
            logger.info("Dry-run trade #%s simulated for %s", trade_id, signal.symbol)
            return TradeExecutionResult(
                trade_id=trade_id,
                executed=True,
                reason="dry_run",
                symbol=signal.symbol,
                direction=signal.direction,
                quote_amount=quote,
                entry_price=signal.entry_price,
                quantity=base_quantity_from_quote(quote, signal.entry_price),
            )

        try:
            return self._execute_live(signal, alert_id, market_context, take_profit)
        except ExchangeError as exc:
            logger.error("Trade execution failed %s: %s", signal.symbol, exc)
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason=f"exchange_error:{exc}",
                symbol=signal.symbol,
                direction=signal.direction,
            )

    def _resolve_quote_amount(self, signal: DIVAPSignal) -> Decimal:
        _, execution, _ = get_active_execution_profile()
        usdt = self._broker.get_usdt_balance()
        quote = calculate_quote_amount(usdt, signal.timeframe, signal.confidence)
        quote = (quote * execution.allocation_multiplier).quantize(Decimal("0.01"))
        min_notional = max(self._broker.min_notional(signal.symbol), MIN_ORDER_USDT)
        return max(quote, min_notional) if quote > 0 else Decimal(0)

    def _execute_live(
        self,
        signal: DIVAPSignal,
        alert_id: int,
        market_context: MarketContext | None,
        take_profit: Decimal,
    ) -> TradeExecutionResult:
        if signal.direction == "buy":
            return self._execute_buy(signal, alert_id, market_context, take_profit)
        return self._execute_sell(signal, alert_id, market_context, take_profit)

    def _execute_buy(
        self,
        signal: DIVAPSignal,
        alert_id: int,
        market_context: MarketContext | None,
        take_profit: Decimal,
    ) -> TradeExecutionResult:
        usdt = self._broker.get_usdt_balance()
        quote = self._resolve_quote_amount(signal)
        min_notional = max(self._broker.min_notional(signal.symbol), MIN_ORDER_USDT)

        if quote < min_notional:
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="insufficient_balance",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        order = self._broker.market_buy_quote(signal.symbol, quote)
        entry_price, quantity, cost = self._broker.parse_filled(order)
        if quantity <= 0:
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="zero_fill",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        stop_order = self._broker.place_stop_loss_limit(
            signal.symbol,
            quantity,
            signal.stop_loss,
            signal.stop_loss * Decimal("0.995"),
        )
        tp_order = self._broker.place_take_profit_limit(
            signal.symbol, quantity, take_profit
        )

        trade_id = self._repo.create_trade(
            alert_id=alert_id,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction,
            confidence=signal.confidence,
            status="open",
            entry_price=entry_price,
            stop_loss=signal.stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            quote_amount=cost or quote,
            context_verdict=(
                market_context.context_verdict if market_context else None
            ),
            context_score=market_context.context_score if market_context else None,
            exchange_order_id=str(order.get("id", "")),
            stop_order_id=str(stop_order["id"]) if stop_order else None,
            tp_order_id=str(tp_order["id"]) if tp_order else None,
            trading_mode=settings.trading_mode,
            opened_at=datetime.now(UTC),
        )

        logger.info("Trade #%s opened BUY %s qty=%s", trade_id, signal.symbol, quantity)
        return TradeExecutionResult(
            trade_id=trade_id,
            executed=True,
            reason="ok",
            symbol=signal.symbol,
            direction=signal.direction,
            quote_amount=cost or quote,
            entry_price=entry_price,
            quantity=quantity,
        )

    def _execute_sell(
        self,
        signal: DIVAPSignal,
        alert_id: int,
        market_context: MarketContext | None,
        take_profit: Decimal,
    ) -> TradeExecutionResult:
        quote_equiv = self._resolve_quote_amount(signal)
        quantity = base_quantity_from_quote(quote_equiv, signal.entry_price)
        base_balance = self._broker.get_base_balance(signal.symbol)
        quantity = min(quantity, base_balance)

        min_notional = max(self._broker.min_notional(signal.symbol), MIN_ORDER_USDT)
        if quantity * signal.entry_price < min_notional:
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="insufficient_base_balance",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        order = self._broker.market_sell(signal.symbol, quantity)
        entry_price, filled_qty, _ = self._broker.parse_filled(order)
        if filled_qty <= 0:
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="zero_fill",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        trade_id = self._repo.create_trade(
            alert_id=alert_id,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction,
            confidence=signal.confidence,
            status="open",
            entry_price=entry_price,
            stop_loss=signal.stop_loss,
            take_profit=take_profit,
            quantity=filled_qty,
            quote_amount=entry_price * filled_qty,
            context_verdict=(
                market_context.context_verdict if market_context else None
            ),
            context_score=market_context.context_score if market_context else None,
            exchange_order_id=str(order.get("id", "")),
            stop_order_id=None,
            tp_order_id=None,
            trading_mode=settings.trading_mode,
            opened_at=datetime.now(UTC),
        )

        logger.info("Trade #%s opened SELL %s qty=%s", trade_id, signal.symbol, filled_qty)
        return TradeExecutionResult(
            trade_id=trade_id,
            executed=True,
            reason="ok",
            symbol=signal.symbol,
            direction=signal.direction,
            quote_amount=entry_price * filled_qty,
            entry_price=entry_price,
            quantity=filled_qty,
        )
