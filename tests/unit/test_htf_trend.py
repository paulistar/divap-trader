from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.context.htf_trend import classify_trend_from_candles, fetch_htf_trends
from src.data.models.candle import Candle


def _candle(close: str, tf: str = "1d") -> Candle:
    price = Decimal(close)
    return Candle(
        symbol="SOLUSDT",
        timeframe=tf,
        timestamp=datetime(2024, 6, 1, tzinfo=UTC),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("1"),
    )


def test_classify_trend_with_five_candles() -> None:
    candles = [_candle(str(100 + i)) for i in range(5)]
    assert classify_trend_from_candles(candles) == "bullish"


def test_classify_trend_unknown_when_too_few() -> None:
    candles = [_candle("100") for _ in range(3)]
    assert classify_trend_from_candles(candles) == "unknown"


@patch("src.context.htf_trend.BinanceSource")
@patch("src.context.htf_trend.build_binance_public_exchange")
def test_fetch_htf_uses_public_exchange(
    mock_public: MagicMock,
    mock_source_cls: MagicMock,
) -> None:
    mock_exchange = MagicMock()
    mock_public.return_value = mock_exchange
    instance = MagicMock()
    mock_source_cls.return_value = instance
    instance.fetch_ohlcv.side_effect = [
        [_candle(str(100 + i), "1d") for i in range(25)],
        [_candle(str(200 - i), "1w") for i in range(25)],
    ]

    trends = fetch_htf_trends("SOLUSDT")

    mock_public.assert_called_once()
    mock_source_cls.assert_called_once_with(exchange=mock_exchange)
    assert trends["1d"] == "bullish"
    assert trends["1w"] == "bearish"
