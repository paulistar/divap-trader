import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from src.context.models import MarketContext
from src.core.config import settings
from src.core.exceptions import ExchangeError
from src.data.repositories.trade_repo import TradeRepository
from src.data.sources.interfaces import MarketDataSource
from src.detection.divap_scanner import DIVAPSignal
from src.execution.interfaces import ExecutionBroker
from src.bankroll.execution_context import (
    get_active_execution_profile,
    get_execution_context,
    get_execution_profile_for,
)
from src.execution.gate import should_execute_trade
from src.markets.factory import get_broker, get_data_source
from src.markets.types import Market, Venue
from src.profiles.models import ProfileExecution
from src.profiles.exit_policy import (
    compute_partial_take_profit_levels,
    resolve_take_profit,
    uses_partial_take_profits,
)
from src.profiles.loader import load_profile
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
        broker: ExecutionBroker | None = None,
        trade_repo: TradeRepository | None = None,
        market_source: MarketDataSource | None = None,
        venue: Venue = Venue.BINANCE,
    ) -> None:
        self._venue = venue
        self._market = Market.CRYPTO if venue == Venue.BINANCE else Market.FOREX
        self._broker = broker or get_broker(venue)
        self._repo = trade_repo or TradeRepository()
        self._source = market_source or get_data_source(venue)

    def try_execute(
        self,
        signal: DIVAPSignal,
        alert_id: int,
        market_context: MarketContext | None,
        profile_id: str | None = None,
    ) -> TradeExecutionResult:
        effective_profile_id = profile_id or get_execution_context()[0]
        profile, execution, meta = get_execution_profile_for(effective_profile_id)
        _, goal_protected = get_execution_context(effective_profile_id)
        candles = self._fetch_candles(signal)
        allowed, reason = should_execute_trade(
            signal,
            market_context,
            settings,
            execution,
            goal_protected=meta.get("protected_mode", False),
            profile=profile,
            candles=candles,
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

        if self._repo.count_open_trades(effective_profile_id) >= execution.max_open_trades:
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="max_open_trades",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        if self._repo.has_open_trade(signal.symbol, signal.timeframe, effective_profile_id):
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="duplicate_open_trade",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        take_profit = (
            resolve_take_profit(signal, profile, candles)
            if profile is not None
            else signal.targets[0]
        )
        if take_profit is None:
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason="no_targets",
                symbol=signal.symbol,
                direction=signal.direction,
            )

        if settings.trading_dry_run:
            quote = self._resolve_quote_amount(signal, execution)
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
                profile_id=effective_profile_id,
                goal_protected=goal_protected,
                market=self._market.value,
                venue=self._venue.value,
            )
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
            return self._execute_live(
                signal,
                alert_id,
                market_context,
                take_profit,
                effective_profile_id,
                goal_protected,
                execution,
            )
        except ExchangeError as exc:
            logger.error("Trade execution failed %s: %s", signal.symbol, exc)
            return TradeExecutionResult(
                trade_id=None,
                executed=False,
                reason=f"exchange_error:{exc}",
                symbol=signal.symbol,
                direction=signal.direction,
            )

    def _fetch_candles(self, signal: DIVAPSignal):
        return self._source.fetch_ohlcv(signal.symbol, signal.timeframe, limit=100)

    def _resolve_quote_amount(
        self, signal: DIVAPSignal, execution: ProfileExecution | None = None
    ) -> Decimal:
        if execution is None:
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
        profile_id: str,
        goal_protected: bool,
        execution: ProfileExecution,
    ) -> TradeExecutionResult:
        if signal.direction == "buy":
            return self._execute_buy(
                signal,
                alert_id,
                market_context,
                take_profit,
                profile_id,
                goal_protected,
                execution,
            )
        return self._execute_sell(
            signal,
            alert_id,
            market_context,
            take_profit,
            profile_id,
            goal_protected,
            execution,
        )

    def _execute_buy(
        self,
        signal: DIVAPSignal,
        alert_id: int,
        market_context: MarketContext | None,
        take_profit: Decimal,
        profile_id: str,
        goal_protected: bool,
        execution: ProfileExecution,
    ) -> TradeExecutionResult:
        usdt = self._broker.get_usdt_balance()
        quote = self._resolve_quote_amount(signal, execution)
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

        profile = load_profile(profile_id)
        tp_levels: tuple[Decimal, ...] | None = None
        tp_order = None
        if profile is not None and uses_partial_take_profits(profile):
            tp_levels = compute_partial_take_profit_levels(
                entry_price,
                take_profit,
                signal.direction,
                profile.exit.partial_take_profits,
            )
        else:
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
            profile_id=profile_id,
            goal_protected=goal_protected,
            market=self._market.value,
            venue=self._venue.value,
            take_profit_levels=tp_levels,
            remaining_quantity=quantity if tp_levels else None,
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
        profile_id: str,
        goal_protected: bool,
        execution: ProfileExecution,
    ) -> TradeExecutionResult:
        quote_equiv = self._resolve_quote_amount(signal, execution)
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
            profile_id=profile_id,
            goal_protected=goal_protected,
            market=self._market.value,
            venue=self._venue.value,
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
