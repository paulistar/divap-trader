from src.markets.instruments import (
    DEFAULT_FOREX_SYMBOLS,
    instrument_from_symbol,
    resolve_instrument,
)
from src.markets.types import Instrument, Market, Venue

__all__ = [
    "DEFAULT_FOREX_SYMBOLS",
    "Instrument",
    "Market",
    "Venue",
    "instrument_from_symbol",
    "resolve_instrument",
]


def __getattr__(name: str):
    if name in {"get_broker", "get_data_source"}:
        from src.markets import factory

        return getattr(factory, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
