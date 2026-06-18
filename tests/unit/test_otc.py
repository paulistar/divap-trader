"""Tests for OTC profile and IQ Option integration."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.core.scan_plan import get_active_scan_plans
from src.otc.config import load_otc_config, resolve_iq_asset
from src.otc.executor import OtcExecutor
from src.otc.models import OtcSignal
from src.otc.signal_parser import parse_telegram_signal
from src.profiles.loader import load_profile


SAMPLE_SIGNAL = """
✅ ENTRADA CONFIRMADA ✅
Ativo: XRP/USDT
Expiração: M1
COMPRA
Entrada: 14:35
Proteção 1: 14:36
"""


def test_otc_profile_exists_and_isolated() -> None:
    profile = load_profile("otc")
    assert profile is not None
    assert profile.id == "otc"
    assert profile.kind == "otc"
    assert profile.scan.enabled is False
    assert profile.execution.max_open_trades == 3


def test_otc_config_loaded_from_yaml() -> None:
    config = load_otc_config()
    assert config.profile_id == "otc"
    assert config.venue == "iqoption"
    assert config.account_mode == "PRACTICE"
    assert config.dry_run is True
    assert config.default_stake_usd == Decimal("5")
    assert config.martingale.enabled is True
    assert config.martingale.max_protections == 2
    assert "XRP/USDT (OTC)" in config.assets


def test_resolve_iq_asset_aliases() -> None:
    config = load_otc_config()
    assert resolve_iq_asset("XRP/USDT", config) == "XRP/USDT (OTC)"
    assert resolve_iq_asset("FORDOTC", config) == "Ford (OTC)"
    assert resolve_iq_asset("BTCUSDT", config) == "BTC/USDT (OTC)"


def test_parse_telegram_signal() -> None:
    signal = parse_telegram_signal(SAMPLE_SIGNAL)
    assert signal is not None
    assert signal.asset == "XRP/USDT"
    assert signal.direction == "buy"
    assert signal.expiry_minutes == 1
    assert signal.protection_level == 1


def test_parse_telegram_signal_venda() -> None:
    text = SAMPLE_SIGNAL.replace("COMPRA", "VENDA")
    signal = parse_telegram_signal(text)
    assert signal is not None
    assert signal.direction == "sell"


def test_active_scan_plans_skip_otc_profile() -> None:
    divap = load_profile("divap")
    assert divap is not None
    mock_settings = MagicMock(
        active_profile_ids=("divap", "otc"),
        active_profile_id="divap",
    )
    with patch("src.core.scan_plan.BankrollRepository") as repo_cls:
        repo_cls.return_value.get_settings.return_value = mock_settings
        plans = get_active_scan_plans()
    profile_ids = {p.profile_id for p in plans}
    assert "divap" in profile_ids
    assert "otc" not in profile_ids


def test_otc_executor_dry_run() -> None:
    signal = OtcSignal(asset="XRP/USDT", direction="buy", expiry_minutes=1)
    broker = MagicMock()
    broker.place_binary.return_value = MagicMock(
        executed=True,
        reason="dry_run",
        trade_id=None,
        order_id=None,
        asset="XRP/USDT (OTC)",
        direction="buy",
        stake_usd=Decimal("5"),
        pnl_usd=None,
        dry_run=True,
    )
    executor = OtcExecutor(broker=broker, trade_repo=MagicMock())
    with patch("src.otc.executor.settings") as mock_settings:
        mock_settings.otc_trading_enabled = False
        result = executor.try_execute(signal)
    assert result.executed is True
    assert result.dry_run is True
    broker.place_binary.assert_called_once()
