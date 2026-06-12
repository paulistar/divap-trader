from __future__ import annotations

import logging
from decimal import Decimal

from src.core.exceptions import ExchangeError
from src.execution.interfaces import ExecutionBroker
from src.markets.fxcm_client import get_fxcm_connection
from src.markets.fxcm_symbols import to_fxcm_symbol
from src.markets.types import Market, Venue

logger = logging.getLogger(__name__)

DEFAULT_MIN_UNITS = 1000


class FxcmBroker(ExecutionBroker):
    """FXCM spot/CFD execution via fxcmpy REST API."""

    @property
    def market(self) -> str:
        return Market.FOREX.value

    @property
    def venue(self) -> str:
        return Venue.FXCM.value

    def _connection(self):
        return get_fxcm_connection()

    def get_usdt_balance(self) -> Decimal:
        try:
            con = self._connection()
            summary = con.get_accounts_summary(kind="dict")
            if not summary:
                return Decimal(0)
            row = summary[0] if isinstance(summary, list) else summary
            equity = row.get("equity") or row.get("balance") or 0
            return Decimal(str(equity))
        except Exception as exc:
            raise ExchangeError(f"Failed to fetch FXCM balance: {exc}") from exc

    def min_notional(self, symbol: str) -> Decimal:
        return Decimal(str(DEFAULT_MIN_UNITS))

    def fetch_ticker_price(self, symbol: str) -> Decimal:
        instrument = to_fxcm_symbol(symbol)
        try:
            con = self._connection()
            prices = con.get_last_price(instrument)
            if isinstance(prices, dict):
                bid = prices.get("Bid")
                ask = prices.get("Ask")
                if bid is not None and ask is not None:
                    return (Decimal(str(bid)) + Decimal(str(ask))) / 2
            raise ExchangeError(f"No price for {symbol}")
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError(f"Failed to fetch FXCM ticker for {symbol}: {exc}") from exc

    def market_buy_units(self, symbol: str, units: int) -> dict:
        instrument = to_fxcm_symbol(symbol)
        try:
            con = self._connection()
            order = con.create_market_buy_order(instrument, int(units))
            return {"id": getattr(order, "order_id", None), "order": order}
        except Exception as exc:
            raise ExchangeError(f"FXCM market buy failed for {symbol}: {exc}") from exc

    def market_sell_units(self, symbol: str, units: int) -> dict:
        instrument = to_fxcm_symbol(symbol)
        try:
            con = self._connection()
            order = con.create_market_sell_order(instrument, int(units))
            return {"id": getattr(order, "order_id", None), "order": order}
        except Exception as exc:
            raise ExchangeError(f"FXCM market sell failed for {symbol}: {exc}") from exc
