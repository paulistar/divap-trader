from __future__ import annotations

from src.core.exceptions import ExchangeError
from src.data.sources.binance import BinanceSource
from src.data.sources.interfaces import MarketDataSource
from src.execution.binance_broker import BinanceBroker
from src.execution.interfaces import ExecutionBroker
from src.markets.types import Market, Venue


def get_data_source(venue: Venue | None = None) -> MarketDataSource:
    selected = venue or Venue.BINANCE
    if selected == Venue.BINANCE:
        return BinanceSource()
    raise ExchangeError(f"Market data source not implemented for venue: {selected.value}")


def get_broker(venue: Venue | None = None) -> ExecutionBroker:
    selected = venue or Venue.BINANCE
    if selected == Venue.BINANCE:
        return BinanceBroker()
    raise ExchangeError(f"Execution broker not implemented for venue: {selected.value}")


def default_venue_for_market(market: Market) -> Venue:
    if market == Market.FOREX:
        return Venue.OANDA
    return Venue.BINANCE
