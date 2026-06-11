from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.data.models.candle import Candle

client = TestClient(app)


def _mock_candles() -> list[Candle]:
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    return [
        Candle(
            symbol="BTCUSDT",
            timeframe="4h",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=i),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("100"),
        )
        for i in range(30)
    ]


@patch("src.api.routes.analysis.DIVAPScanner")
@patch("src.api.routes.analysis.BinanceSource")
@patch("src.api.routes.analysis.CandleRepository")
def test_analyze_no_signal(mock_repo, mock_source, mock_scanner) -> None:
    mock_source.return_value.fetch_ohlcv.return_value = _mock_candles()
    mock_scanner.return_value.scan.return_value = None
    mock_repo.return_value.upsert_many.return_value = 30

    response = client.post("/analyze/BTCUSDT?timeframe=4h&with_llm=false")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["signal"] is None


@patch("src.api.deps.settings")
def test_analyze_requires_api_key_in_production(mock_settings) -> None:
    mock_settings.app_env = "production"
    mock_settings.api_key = "secret-key"

    response = client.post("/analyze/BTCUSDT?timeframe=4h")
    assert response.status_code == 401

    response = client.post(
        "/analyze/BTCUSDT?timeframe=4h",
        headers={"X-API-Key": "secret-key"},
    )
    # May fail on binance without mock but auth passes
    assert response.status_code != 401
