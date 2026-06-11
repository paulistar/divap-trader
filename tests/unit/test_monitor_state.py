"""Tests for profile-aware position monitor scheduling."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.core.monitor_state import record_monitor, should_run_monitor
from src.core.scan_plan import ScanPlan, should_run_interval
from src.profiles.loader import load_profile


def test_caixa_rapido_monitor_interval_two_minutes() -> None:
    profile = load_profile("caixa_rapido")
    assert profile is not None
    assert profile.scan.monitor_interval_seconds == 120


def test_should_run_interval_respects_monitor_cadence() -> None:
    now = datetime.now(UTC)
    assert should_run_interval(120, now - timedelta(seconds=60), now) is False
    assert should_run_interval(120, now - timedelta(seconds=121), now) is True


def test_should_run_monitor_when_never_run() -> None:
    plan = ScanPlan(
        profile_id="caixa_rapido",
        profile_name="Caixa rápido",
        interval_seconds=300,
        monitor_interval_seconds=120,
        timeframes=("15m", "1h"),
        symbols=("BTCUSDT",),
    )
    with patch("src.core.monitor_state.get_active_scan_plan", return_value=plan):
        with patch("src.core.monitor_state.get_last_monitor_at", return_value=None):
            assert should_run_monitor() is True


def test_record_monitor_persists_result() -> None:
    mock_client = MagicMock()
    with patch("src.core.monitor_state._client", return_value=mock_client):
        record_monitor("caixa_rapido", {"checked": 2, "closed": 0, "errors": 0})
    assert mock_client.set.call_count == 2
