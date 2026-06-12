from src.core.timeframes import CRYPTO_TIMEFRAMES, is_ltf
from src.data.sources.binance import TIMEFRAME_MAP


def test_binance_supports_scalp_and_weekly() -> None:
    for tf in ("1m", "5m", "15m", "1h", "4h", "1d", "1w"):
        assert tf in TIMEFRAME_MAP
        assert tf in CRYPTO_TIMEFRAMES


def test_is_ltf() -> None:
    assert is_ltf("1m") is True
    assert is_ltf("5m") is True
    assert is_ltf("4h") is False
    assert is_ltf("1w") is False
