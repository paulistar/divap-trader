from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Market(StrEnum):
    CRYPTO = "crypto"
    FOREX = "forex"


class Venue(StrEnum):
    BINANCE = "binance"
    FXCM = "fxcm"
    OANDA = "oanda"


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
