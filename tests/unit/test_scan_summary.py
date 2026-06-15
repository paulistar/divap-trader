"""Unit tests for scan metrics and scan state summary."""

from unittest.mock import MagicMock, patch

from src.core.scan_metrics import ScanMetrics
from src.core.scan_state import get_scan_status, record_scan


def test_scan_metrics_to_dict() -> None:
    m = ScanMetrics()
    m.pairs_scanned = 8
    m.setups_detected = 2
    m.record_gate_block("confidence_below_threshold")
    data = m.to_dict()
    assert data["pairs_scanned"] == 8
    assert data["gate_blocks"]["confidence_below_threshold"] == 1


def test_record_scan_stores_summary() -> None:
    mock_client = MagicMock()
    with patch("src.core.scan_state._client", return_value=mock_client):
        record_scan(
            "divap",
            {
                "signals": 1,
                "errors": 0,
                "details": ["BTCUSDT:4h"],
                "summary": {"pairs_scanned": 4, "gate_blocks": {}},
            },
        )
    payload = mock_client.set.call_args_list[3][0][1]
    assert "summary" in payload


def test_get_scan_status_includes_summary() -> None:
    mock_client = MagicMock()
    plan = MagicMock(
        profile_id="divap",
        profile_name="DIVAP",
        interval_seconds=900,
        monitor_interval_seconds=300,
        timeframes=("1h",),
        symbols=("BTCUSDT",),
    )
    settings = MagicMock(active_profile_ids=("divap",), active_profile_id="divap")
    mock_client.get.side_effect = [
        "2026-06-11T12:00:00+00:00",
        '{"signals": 1, "summary": {"pairs_scanned": 4}}',
        None,
        None,
    ]
    with patch("src.core.scan_state._client", return_value=mock_client):
        with patch("src.core.beat_state._client", return_value=mock_client):
            with patch("src.core.scan_state.get_active_scan_plans", return_value=(plan,)):
                with patch("src.core.scan_state.BankrollRepository") as repo_cls:
                    repo_cls.return_value.get_settings.return_value = settings
                    with patch("src.core.monitor_state.get_active_scan_plan", return_value=plan):
                        with patch("src.core.monitor_state._client", return_value=mock_client):
                            with patch("src.core.scan_state.get_beat_status", return_value={}):
                                status = get_scan_status()
    assert status["summary"]["pairs_scanned"] == 4
