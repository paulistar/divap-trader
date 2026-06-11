#!/usr/bin/env python3
"""Backfill OHLCV candles from Binance into TimescaleDB."""

import argparse
import sys

from src.core.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES
from src.core.exceptions import ExchangeError
from src.data.repositories.candle_repo import CandleRepository
from src.data.sources.binance import BinanceSource


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill candles from Binance")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=list(DEFAULT_SYMBOLS),
        help="Symbols e.g. BTCUSDT ETHUSDT",
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=list(DEFAULT_TIMEFRAMES),
        help="Timeframes e.g. 1h 4h 1d",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Number of candles per symbol/timeframe",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = BinanceSource()
    repo = CandleRepository()
    total = 0

    for symbol in args.symbols:
        for timeframe in args.timeframes:
            try:
                candles = source.fetch_ohlcv(symbol, timeframe, limit=args.limit)
                count = repo.upsert_many(candles)
                total += count
                print(f"✓ {symbol} {timeframe}: {count} candles")
            except ExchangeError as exc:
                print(f"✗ {symbol} {timeframe}: {exc}", file=sys.stderr)

    print(f"Done. {total} candles upserted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
