from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.context.fear_greed import fetch_fear_greed
from src.context.htf_trend import classify_trend_from_candles
from src.context.models import FearGreedReading, GlobalMarketSnapshot, MacroIndexSnapshot
from src.context.scoring import assess_market_context
from src.context.models import MarketContextParts
from src.data.models.candle import Candle
from datetime import UTC, datetime


def _candle(close: str) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol="BTCUSDT",
        timeframe="1d",
        timestamp=datetime(2024, 6, 1, tzinfo=UTC),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("1"),
    )


def test_classify_trend_bullish() -> None:
    candles = [_candle(str(100 + i)) for i in range(25)]
    assert classify_trend_from_candles(candles) == "bullish"


def test_classify_trend_bearish() -> None:
    candles = [_candle(str(200 - i)) for i in range(25)]
    assert classify_trend_from_candles(candles) == "bearish"


@patch("src.context.fear_greed.httpx.Client")
def test_fetch_fear_greed(mock_client_cls: MagicMock) -> None:
    mock_http = MagicMock()
    mock_client_cls.return_value = mock_http
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"value": "42", "value_classification": "Fear", "timestamp": "1710000000"}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_http.get.return_value = mock_response

    result = fetch_fear_greed()
    assert result == FearGreedReading(value=42, classification="Fear", timestamp="1710000000")


def test_assess_market_context_extreme_greed_buy() -> None:
    parts = MarketContextParts(
        fear_greed=FearGreedReading(85, "Extreme Greed", "1"),
        htf_trends={"1d": "bullish", "1w": "bullish"},
    )
    score, verdict, flags = assess_market_context(
        "BTCUSDT", "4h", "buy", parts
    )
    assert "extreme_greed" in flags
    assert score < 65
    assert verdict in ("caution", "reject")


def test_assess_market_context_aligned_htf() -> None:
    parts = MarketContextParts(
        fear_greed=FearGreedReading(50, "Neutral", "1"),
        htf_trends={"1d": "bullish", "1w": "bullish"},
        macro_indices=(
            MacroIndexSnapshot("SPY", "S&P 500", 1.2, "bullish"),
        ),
    )
    score, verdict, flags = assess_market_context(
        "BTCUSDT", "4h", "buy", parts
    )
    assert score >= 55
    assert "htf_1d_aligned_bullish" in flags
    assert verdict in ("confirm", "caution")
