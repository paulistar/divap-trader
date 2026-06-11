from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal


class ExecutionBroker(ABC):
    """Abstract order execution — Binance MVP, OANDA roadmap."""

    @property
    @abstractmethod
    def market(self) -> str:
        """Primary market: crypto | forex."""

    @property
    @abstractmethod
    def venue(self) -> str:
        """Exchange/broker: binance | oanda."""

    @abstractmethod
    def get_usdt_balance(self) -> Decimal:
        """Free quote balance for sizing (USDT on Binance, USD on OANDA)."""

    @abstractmethod
    def min_notional(self, symbol: str) -> Decimal:
        """Minimum order size in quote currency."""

    @abstractmethod
    def fetch_ticker_price(self, symbol: str) -> Decimal:
        """Latest tradable price for symbol."""
