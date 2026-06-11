from datetime import UTC, datetime
from decimal import Decimal

import ccxt

from src.core.exceptions import ExchangeError
from src.data.sources.binance_exchange import build_binance_exchange
from src.data.models.candle import Candle
from src.data.sources.interfaces import ExchangeSource

# ccxt timeframe keys
TIMEFRAME_MAP: dict[str, str] = {
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
}


def to_ccxt_symbol(symbol: str) -> str:
    """BTCUSDT -> BTC/USDT"""
    if "/" in symbol:
        return symbol
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"{base}/USDT"
    raise ExchangeError(f"Unsupported symbol format: {symbol}")


def from_ccxt_symbol(ccxt_symbol: str) -> str:
    """BTC/USDT -> BTCUSDT"""
    return ccxt_symbol.replace("/", "")


def parse_ohlcv_row(symbol: str, timeframe: str, row: list) -> Candle:
    ts_ms, open_, high, low, close, volume = row
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=UTC),
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
    )


class BinanceSource(ExchangeSource):
    def __init__(self, exchange: ccxt.binance | None = None) -> None:
        self._exchange = exchange or self._build_exchange()

    def _build_exchange(self):
        return build_binance_exchange()

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        if timeframe not in TIMEFRAME_MAP:
            raise ExchangeError(f"Unsupported timeframe: {timeframe}")

        ccxt_symbol = to_ccxt_symbol(symbol)
        ccxt_tf = TIMEFRAME_MAP[timeframe]
        normalized_symbol = from_ccxt_symbol(ccxt_symbol)

        try:
            raw = self._exchange.fetch_ohlcv(ccxt_symbol, ccxt_tf, limit=limit)
        except ccxt.BaseError as exc:
            raise ExchangeError(f"Binance fetch failed for {symbol}: {exc}") from exc

        return [parse_ohlcv_row(normalized_symbol, timeframe, row) for row in raw]
