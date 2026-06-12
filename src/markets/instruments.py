from __future__ import annotations

from src.markets.types import Instrument, Market, Venue

DEFAULT_FOREX_SYMBOLS: tuple[str, ...] = (
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "XAU_USD",
)

_FOREX_SYMBOLS = set(DEFAULT_FOREX_SYMBOLS)


def instrument_from_symbol(
    symbol: str,
    *,
    market: Market | None = None,
    venue: Venue | None = None,
) -> Instrument:
    normalized = symbol.strip().upper().replace("/", "_")
    if market is None:
        if normalized in _FOREX_SYMBOLS or "_" in normalized and not normalized.endswith("USDT"):
            market = Market.FOREX
        else:
            market = Market.CRYPTO
    if venue is None:
        venue = Venue.FXCM if market == Market.FOREX else Venue.BINANCE
    if market == Market.CRYPTO:
        normalized = normalized.replace("_", "")
    return Instrument(market=market, venue=venue, symbol=normalized)


def resolve_instrument(
    symbol: str,
    market: Market | str | None = None,
    venue: Venue | str | None = None,
) -> Instrument:
    parsed_market = Market(market) if isinstance(market, str) else market
    parsed_venue = Venue(venue) if isinstance(venue, str) else venue
    return instrument_from_symbol(symbol, market=parsed_market, venue=parsed_venue)
