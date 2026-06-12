"""Tests for profile-aware scan planning."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from decimal import Decimal

from src.core.scan_plan import ScanPlan, get_active_scan_plan, should_run_scan
from src.profiles.loader import load_profile


def test_scalper_includes_15m_and_fast_interval() -> None:
    profile = load_profile("scalper")
    assert profile is not None
    assert profile.scan.interval_seconds == 300
    assert profile.scan.monitor_interval_seconds == 120
    assert "15m" in profile.scan.timeframes
    assert "1h" in profile.scan.timeframes
    assert profile.scan.symbols is not None
    assert "BTCUSDT" in profile.scan.symbols


def test_divap_scan_top20_crypto() -> None:
    profile = load_profile("divap")
    assert profile is not None
    assert profile.scan.interval_seconds == 900
    assert profile.scan.timeframes == ("1h", "4h", "1d")
    assert profile.scan.symbols is not None
    assert len(profile.scan.symbols) == 20
    assert profile.execution.min_risk_reward == Decimal("1.5")


def test_position_trader_long_term() -> None:
    profile = load_profile("position")
    assert profile is not None
    assert profile.scan.timeframes == ("4h", "1d")
    assert profile.scan.interval_seconds == 3600
    assert profile.execution.min_risk_reward >= Decimal("2.0")


def test_anti_divap_contrarian() -> None:
    profile = load_profile("anti_divap")
    assert profile is not None
    assert profile.execution.block_on_reject is False
    assert profile.scan.symbols == ("BTCUSDT", "ETHUSDT")


def test_should_run_scan_when_never_scanned() -> None:
    plan = ScanPlan(
        profile_id="caixa_rapido",
        profile_name="Caixa rápido",
        interval_seconds=300,
        monitor_interval_seconds=120,
        timeframes=("15m", "1h"),
        symbols=("BTCUSDT", "ETHUSDT"),
    )
    assert should_run_scan(plan, None, datetime.now(UTC)) is True


def test_should_run_scan_respects_interval() -> None:
    plan = ScanPlan(
        profile_id="divap",
        profile_name="DIVAP",
        interval_seconds=900,
        monitor_interval_seconds=300,
        timeframes=("1h",),
        symbols=("BTCUSDT",),
    )
    now = datetime.now(UTC)
    recent = now - timedelta(seconds=120)
    assert should_run_scan(plan, recent, now) is False
    old = now - timedelta(seconds=901)
    assert should_run_scan(plan, old, now) is True


def test_get_active_scan_plan_uses_bankroll_profile() -> None:
    profile = load_profile("scalper")
    assert profile is not None
    mock_settings = MagicMock(active_profile_id="scalper", goal_reached_at=None)
    with patch("src.core.scan_plan.BankrollRepository") as repo_cls:
        repo_cls.return_value.get_settings.return_value = mock_settings
        with patch("src.core.scan_plan.load_profile", return_value=profile):
            plan = get_active_scan_plan()
    assert plan.profile_id == "scalper"
    assert "15m" in plan.timeframes
    assert plan.monitor_interval_seconds == 120
