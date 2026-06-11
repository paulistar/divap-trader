from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import ExchangeError
from src.data.sources.binance import BinanceSource
from src.execution.binance_broker import BinanceBroker
from src.markets.factory import get_broker, get_data_source
from src.markets.instruments import instrument_from_symbol
from src.markets.types import Market, Venue


def test_instrument_from_crypto_symbol() -> None:
    inst = instrument_from_symbol("BTCUSDT")
    assert inst.market == Market.CRYPTO
    assert inst.venue == Venue.BINANCE
    assert inst.symbol == "BTCUSDT"


def test_instrument_from_forex_symbol() -> None:
    inst = instrument_from_symbol("EUR_USD")
    assert inst.market == Market.FOREX
    assert inst.venue == Venue.OANDA
    assert inst.symbol == "EUR_USD"


def test_get_data_source_binance() -> None:
    source = get_data_source(Venue.BINANCE)
    assert isinstance(source, BinanceSource)


def test_get_broker_binance() -> None:
    broker = get_broker(Venue.BINANCE)
    assert isinstance(broker, BinanceBroker)
    assert broker.market == Market.CRYPTO.value
    assert broker.venue == Venue.BINANCE.value


def test_get_broker_oanda_not_implemented() -> None:
    with pytest.raises(ExchangeError, match="oanda"):
        get_broker(Venue.OANDA)


def test_trade_executor_uses_factory_by_default() -> None:
    from src.execution.trade_executor import TradeExecutor

    with patch("src.execution.trade_executor.get_broker") as mock_broker, patch(
        "src.execution.trade_executor.get_data_source"
    ) as mock_source:
        mock_broker.return_value = MagicMock()
        mock_source.return_value = MagicMock()
        TradeExecutor()
        mock_broker.assert_called_once_with(Venue.BINANCE)
        mock_source.assert_called_once_with(Venue.BINANCE)
