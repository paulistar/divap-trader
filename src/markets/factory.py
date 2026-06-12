from __future__ import annotations

from src.core.exceptions import ExchangeError
from src.data.sources.interfaces import MarketDataSource
from src.execution.interfaces import ExecutionBroker
from src.markets.types import Market, Venue


def get_data_source(venue: Venue | None = None) -> MarketDataSource:
    selected = venue or Venue.BINANCE
    if selected == Venue.BINANCE:
        from src.data.sources.binance import BinanceSource

        return BinanceSource()
    if selected == Venue.FXCM:
        from src.data.sources.fxcm import FxcmSource

        return FxcmSource()
    raise ExchangeError(f"Market data source not implemented for venue: {selected.value}")


def get_broker(venue: Venue | None = None) -> ExecutionBroker:
    selected = venue or Venue.BINANCE
    if selected == Venue.BINANCE:
        from src.execution.binance_broker import BinanceBroker

        return BinanceBroker()
    if selected == Venue.FXCM:
        from src.execution.fxcm_broker import FxcmBroker

        return FxcmBroker()
    raise ExchangeError(f"Execution broker not implemented for venue: {selected.value}")


def default_venue_for_market(market: Market) -> Venue:
    if market == Market.FOREX:
        return Venue.FXCM
    return Venue.BINANCE
