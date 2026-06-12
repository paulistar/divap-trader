from __future__ import annotations

from datetime import UTC
from decimal import Decimal

import pandas as pd

from src.core.exceptions import ExchangeError
from src.data.models.candle import Candle
from src.data.sources.interfaces import MarketDataSource
from src.markets.fxcm_client import get_fxcm_connection
from src.markets.fxcm_symbols import from_fxcm_symbol, to_fxcm_period, to_fxcm_symbol


def _row_to_candle(symbol: str, timeframe: str, row: pd.Series) -> Candle:
    ts = row.name if hasattr(row, "name") else row.get("date")
    if ts is None:
        raise ExchangeError("FXCM candle sem timestamp")
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=UTC)

    def _price(prefix: str) -> Decimal:
        for col in (f"{prefix}close", f"{prefix}open"):
            if col in row and pd.notna(row[col]):
                return Decimal(str(row[col]))
        raise ExchangeError(f"FXCM candle sem preço {prefix}")

    bid = _price("bid")
    ask = _price("ask")
    mid = (bid + ask) / 2
    high_bid = Decimal(str(row.get("bidhigh", mid)))
    low_bid = Decimal(str(row.get("bidlow", mid)))
    high_ask = Decimal(str(row.get("askhigh", mid)))
    low_ask = Decimal(str(row.get("asklow", mid)))
    high = max(high_bid, high_ask)
    low = min(low_bid, low_ask)
    open_ = (Decimal(str(row.get("bidopen", mid))) + Decimal(str(row.get("askopen", mid)))) / 2
    volume = Decimal(str(row.get("tickqty", 0) or 0))

    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts,
        open=open_,
        high=high,
        low=low,
        close=mid,
        volume=volume,
    )


class FxcmSource(MarketDataSource):
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        instrument = to_fxcm_symbol(symbol)
        period = to_fxcm_period(timeframe)
        normalized = from_fxcm_symbol(instrument)

        try:
            con = get_fxcm_connection()
            df = con.get_candles(
                instrument=instrument,
                period=period,
                number=limit,
                columns=["bidopen", "bidhigh", "bidlow", "bidclose",
                         "askopen", "askhigh", "asklow", "askclose", "tickqty"],
            )
        except Exception as exc:
            raise ExchangeError(f"FXCM fetch failed for {symbol} {timeframe}: {exc}") from exc

        if df is None or df.empty:
            return []

        candles: list[Candle] = []
        for _, row in df.iterrows():
            try:
                candles.append(_row_to_candle(normalized, timeframe, row))
            except ExchangeError:
                continue
        return candles
