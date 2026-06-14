import logging
from decimal import Decimal

from src.core.exceptions import ExchangeError
from src.data.sources.binance import from_ccxt_symbol, to_ccxt_symbol
from src.data.sources.binance_exchange import build_binance_exchange
from src.execution.interfaces import ExecutionBroker
from src.markets.types import Market, Venue

logger = logging.getLogger(__name__)


class BinanceBroker(ExecutionBroker):
    """Spot order execution via ccxt (testnet when configured)."""

    @property
    def market(self) -> str:
        return Market.CRYPTO.value

    @property
    def venue(self) -> str:
        return Venue.BINANCE.value

    def __init__(self, exchange=None) -> None:
        self._exchange = exchange
        self._markets_loaded = exchange is not None

    @property
    def exchange(self):
        if self._exchange is None:
            self._exchange = build_binance_exchange()
        if not self._markets_loaded:
            self._exchange.load_markets()
            self._markets_loaded = True
        return self._exchange

    def get_usdt_balance(self) -> Decimal:
        try:
            balance = self.exchange.fetch_balance()
        except Exception as exc:
            raise ExchangeError(f"Failed to fetch balance: {exc}") from exc
        free = balance.get("USDT", {}).get("free", 0)
        return Decimal(str(free))

    def get_base_balance(self, symbol: str) -> Decimal:
        base = symbol.replace("USDT", "")
        try:
            balance = self.exchange.fetch_balance()
        except Exception as exc:
            raise ExchangeError(f"Failed to fetch balance: {exc}") from exc
        free = balance.get(base, {}).get("free", 0)
        return Decimal(str(free))

    def min_notional(self, symbol: str) -> Decimal:
        ccxt_sym = to_ccxt_symbol(symbol)
        market = self.exchange.market(ccxt_sym)
        limits = market.get("limits", {})
        cost = limits.get("cost", {})
        min_cost = cost.get("min")
        if min_cost is not None:
            return Decimal(str(min_cost))
        return Decimal("10")

    def market_buy_quote(self, symbol: str, quote_amount: Decimal) -> dict:
        ccxt_sym = to_ccxt_symbol(symbol)
        try:
            return self.exchange.create_order(
                ccxt_sym,
                "market",
                "buy",
                None,
                None,
                {"quoteOrderQty": float(quote_amount)},
            )
        except Exception as exc:
            raise ExchangeError(f"Market buy failed for {symbol}: {exc}") from exc

    def market_sell(self, symbol: str, quantity: Decimal) -> dict:
        ccxt_sym = to_ccxt_symbol(symbol)
        try:
            return self.exchange.create_order(
                ccxt_sym,
                "market",
                "sell",
                float(quantity),
            )
        except Exception as exc:
            raise ExchangeError(f"Market sell failed for {symbol}: {exc}") from exc

    def place_stop_loss_limit(
        self,
        symbol: str,
        quantity: Decimal,
        stop_price: Decimal,
        limit_price: Decimal,
    ) -> dict | None:
        ccxt_sym = to_ccxt_symbol(symbol)
        try:
            return self.exchange.create_order(
                ccxt_sym,
                "stop_loss_limit",
                "sell",
                float(quantity),
                float(limit_price),
                {"stopPrice": float(stop_price)},
            )
        except Exception as exc:
            logger.warning("Stop loss order failed for %s: %s", symbol, exc)
            return None

    def place_take_profit_limit(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
    ) -> dict | None:
        ccxt_sym = to_ccxt_symbol(symbol)
        try:
            return self.exchange.create_order(
                ccxt_sym,
                "limit",
                "sell",
                float(quantity),
                float(price),
            )
        except Exception as exc:
            logger.warning("Take profit order failed for %s: %s", symbol, exc)
            return None

    def cancel_order(self, symbol: str, order_id: str) -> None:
        ccxt_sym = to_ccxt_symbol(symbol)
        try:
            self.exchange.cancel_order(order_id, ccxt_sym)
        except Exception as exc:
            logger.warning("Cancel order failed for %s (%s): %s", symbol, order_id, exc)

    def fetch_order(self, symbol: str, order_id: str) -> dict:
        ccxt_sym = to_ccxt_symbol(symbol)
        try:
            return self.exchange.fetch_order(order_id, ccxt_sym)
        except Exception as exc:
            raise ExchangeError(f"Failed to fetch order {order_id}: {exc}") from exc

    def fetch_ticker_price(self, symbol: str) -> Decimal:
        ccxt_sym = to_ccxt_symbol(symbol)
        try:
            ticker = self.exchange.fetch_ticker(ccxt_sym)
        except Exception as exc:
            raise ExchangeError(f"Failed to fetch ticker for {symbol}: {exc}") from exc
        last = ticker.get("last") or ticker.get("close")
        if last is None:
            raise ExchangeError(f"No price for {symbol}")
        return Decimal(str(last))

    @staticmethod
    def parse_filled(order: dict) -> tuple[Decimal, Decimal, Decimal]:
        """Return (avg_price, filled_qty, cost)."""
        avg = order.get("average") or order.get("price")
        filled = order.get("filled") or order.get("amount") or 0
        cost = order.get("cost") or 0
        if avg is None and cost and filled:
            avg = float(cost) / float(filled)
        return (
            Decimal(str(avg or 0)),
            Decimal(str(filled or 0)),
            Decimal(str(cost or 0)),
        )

    @staticmethod
    def normalize_symbol(order: dict) -> str:
        sym = order.get("symbol", "")
        return from_ccxt_symbol(sym) if "/" in sym else sym
