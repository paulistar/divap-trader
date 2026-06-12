import pytest

from src.markets.fxcm_symbols import from_fxcm_symbol, to_fxcm_period, to_fxcm_symbol
from src.markets.instruments import instrument_from_symbol
from src.markets.types import Market, Venue


def test_to_fxcm_symbol() -> None:
    assert to_fxcm_symbol("EUR_USD") == "EUR/USD"
    assert to_fxcm_symbol("EUR/USD") == "EUR/USD"


def test_from_fxcm_symbol() -> None:
    assert from_fxcm_symbol("EUR/USD") == "EUR_USD"


def test_to_fxcm_period() -> None:
    assert to_fxcm_period("15m") == "m15"
    assert to_fxcm_period("1h") == "H1"


def test_to_fxcm_period_invalid() -> None:
    with pytest.raises(ValueError):
        to_fxcm_period("2h")


def test_forex_defaults_to_fxcm_venue() -> None:
    inst = instrument_from_symbol("EUR_USD")
    assert inst.market == Market.FOREX
    assert inst.venue == Venue.FXCM
