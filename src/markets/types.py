from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Market(StrEnum):
    CRYPTO = "crypto"
    FOREX = "forex"
    BINARY_OTC = "binary_otc"


class Venue(StrEnum):
    BINANCE = "binance"
    FXCM = "fxcm"
    OANDA = "oanda"
    IQ_OPTION = "iqoption"


@dataclass(frozen=True, slots=True)
class Instrument:
    """Normalized tradable instrument across venues."""

    market: Market
    venue: Venue
    symbol: str

    @property
    def market_value(self) -> str:
        return self.market.value

    @property
    def venue_value(self) -> str:
        return self.venue.value
