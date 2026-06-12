"""Timeframes suportados na plataforma crypto (Binance spot)."""

from typing import Literal

CryptoTimeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"]

CRYPTO_TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1d", "1w")

SCALP_TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "1h")

SWING_TIMEFRAMES: tuple[str, ...] = ("1h", "4h", "1d")

POSITION_TIMEFRAMES: tuple[str, ...] = ("4h", "1d", "1w")

LTF_TIMEFRAMES: frozenset[str] = frozenset({"1m", "5m", "15m", "1h"})


def is_ltf(timeframe: str) -> bool:
    return timeframe in LTF_TIMEFRAMES
