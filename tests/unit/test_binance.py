from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.core.exceptions import ExchangeError
from src.data.sources.binance import (
    from_ccxt_symbol,
    parse_ohlcv_row,
    to_ccxt_symbol,
)


def test_to_ccxt_symbol() -> None:
    assert to_ccxt_symbol("BTCUSDT") == "BTC/USDT"
    assert to_ccxt_symbol("ETH/USDT") == "ETH/USDT"


def test_to_ccxt_symbol_invalid() -> None:
    with pytest.raises(ExchangeError):
        to_ccxt_symbol("BTCBRL")


def test_from_ccxt_symbol() -> None:
    assert from_ccxt_symbol("BTC/USDT") == "BTCUSDT"


def test_parse_ohlcv_row() -> None:
    ts = int(datetime(2024, 6, 1, 12, 0, tzinfo=UTC).timestamp() * 1000)
    row = [ts, 100.0, 105.0, 99.0, 103.0, 1234.56]
    candle = parse_ohlcv_row("BTCUSDT", "1h", row)

    assert candle.symbol == "BTCUSDT"
    assert candle.timeframe == "1h"
    assert candle.open == Decimal("100.0")
    assert candle.close == Decimal("103.0")
    assert candle.volume == Decimal("1234.56")
