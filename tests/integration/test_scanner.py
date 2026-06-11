from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from src.data.models.candle import Candle
from src.detection.divap_scanner import DIVAPScanner
from src.detection.divergence import DivergenceResult
def _make_candles(n: int = 30) -> list[Candle]:
    return [
        Candle(
            symbol="BTCUSDT",
            timeframe="1h",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=i),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("100"),
        )
        for i in range(n)
    ]


@patch("src.detection.divap_scanner.detect_divergence")
@patch("src.detection.divap_scanner.check_volume_confirmation")
@patch("src.detection.divap_scanner.check_fibonacci_zone")
@patch("src.detection.divap_scanner.check_reversal_pattern")
@patch("src.detection.divap_scanner.compute_rsi_series")
def test_scanner_returns_signal_with_four_confluences(
    mock_rsi,
    mock_pattern,
    mock_fibo,
    mock_volume,
    mock_divergence,
) -> None:
    mock_rsi.return_value = [50.0] * 30
    mock_divergence.return_value = DivergenceResult(
        divergence_type="bullish",
        price_pivot_1=Decimal("100"),
        price_pivot_2=Decimal("90"),
        rsi_pivot_1=25.0,
        rsi_pivot_2=32.0,
        pivot_index_1=10,
        pivot_index_2=20,
    )
    mock_volume.return_value = True
    mock_fibo.return_value = (Decimal("1.0"), Decimal("100"))
    mock_pattern.return_value = "hammer"

    scanner = DIVAPScanner()
    signal = scanner.scan("BTCUSDT", "1h", _make_candles())

    assert signal is not None
    assert signal.direction == "buy"
    assert signal.confidence == "high"
    assert signal.criteria.count == 4


@patch("src.detection.divap_scanner.detect_divergence")
@patch("src.detection.divap_scanner.compute_rsi_series")
def test_scanner_returns_none_without_divergence(mock_rsi, mock_divergence) -> None:
    mock_rsi.return_value = [50.0] * 30
    mock_divergence.return_value = None

    scanner = DIVAPScanner()
    assert scanner.scan("BTCUSDT", "1h", _make_candles()) is None
