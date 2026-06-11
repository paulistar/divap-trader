from unittest.mock import MagicMock, patch

from src.api.dashboard_service import execution_reason_for_alert
from src.core.scan_state import get_scan_status, record_scan
from src.data.repositories.alert_repo import AlertRecord


def test_execution_reason_medium_confidence() -> None:
    alert = AlertRecord(
        id=1,
        symbol="SOLUSDT",
        timeframe="4h",
        direction="buy",
        confidence="medium",
        criteria={},
        entry_price=None,
        stop_loss=None,
        targets=[],
        rsi_value=None,
        volume_ratio=None,
        divergence_type=None,
        pattern_detected=None,
        fibo_level=None,
        acknowledged=False,
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    with patch("src.api.dashboard_service.settings") as mock_settings:
        mock_settings.trading_enabled = True
        mock_settings.trading_min_confidence = "high"
        mock_settings.trading_block_on_context_reject = True
        assert execution_reason_for_alert(alert) == "Não opera — confiança média"


def test_record_and_get_scan_status() -> None:
    mock_client = MagicMock()
    mock_client.get.side_effect = [None, None]
    with patch("src.core.scan_state._client", return_value=mock_client):
        record_scan({"signals": 2, "errors": 0, "details": ["BTCUSDT:4h"]})
        assert mock_client.set.call_count == 2

    mock_client.get.side_effect = [
        "2026-06-11T12:00:00+00:00",
        '{"signals": 2, "errors": 0}',
        None,
    ]
    with patch("src.core.scan_state._client", return_value=mock_client):
        with patch("src.core.beat_state._client", return_value=mock_client):
            status = get_scan_status()
        assert status["last_signals"] == 2
        assert status["interval_seconds"] == 900
