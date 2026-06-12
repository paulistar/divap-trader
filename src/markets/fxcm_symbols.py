from __future__ import annotations

TIMEFRAME_TO_FXCM: dict[str, str] = {
    "15m": "m15",
    "1h": "H1",
    "4h": "H4",
    "1d": "D1",
    "1w": "W1",
}

FXCM_TO_TIMEFRAME: dict[str, str] = {v: k for k, v in TIMEFRAME_TO_FXCM.items()}


def to_fxcm_symbol(symbol: str) -> str:
    """EUR_USD -> EUR/USD"""
    normalized = symbol.strip().upper().replace("-", "_")
    if "/" in normalized:
        return normalized
    if "_" in normalized:
        base, quote = normalized.split("_", 1)
        return f"{base}/{quote}"
    if len(normalized) == 6:
        return f"{normalized[:3]}/{normalized[3:]}"
    return normalized


def from_fxcm_symbol(symbol: str) -> str:
    """EUR/USD -> EUR_USD"""
    return symbol.strip().upper().replace("/", "_")


def to_fxcm_period(timeframe: str) -> str:
    key = timeframe.strip().lower()
    if key not in TIMEFRAME_TO_FXCM:
        raise ValueError(f"Unsupported FXCM timeframe: {timeframe}")
    return TIMEFRAME_TO_FXCM[key]
