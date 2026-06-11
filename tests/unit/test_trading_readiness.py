from unittest.mock import MagicMock, patch

from src.core.beat_state import get_beat_status, record_beat_heartbeat
from src.trading.readiness import build_trading_readiness


def test_record_and_get_beat_status() -> None:
    mock_client = MagicMock()
    with patch("src.core.beat_state._client", return_value=mock_client):
        record_beat_heartbeat()
        assert mock_client.set.call_count == 1

    mock_client.get.return_value = "2026-06-11T12:00:00+00:00"
    with patch("src.core.beat_state._client", return_value=mock_client):
        with patch("src.core.beat_state.datetime") as mock_dt:
            mock_dt.now.return_value = __import__("datetime").datetime(
                2026, 6, 11, 12, 1, 0, tzinfo=__import__("datetime").UTC
            )
            mock_dt.fromisoformat = __import__("datetime").datetime.fromisoformat
            mock_dt.UTC = __import__("datetime").UTC
            status = get_beat_status()
    assert status["beat_active"] is True
    assert status["beat_seconds_since"] == 60


def test_trading_readiness_when_disabled() -> None:
    with patch("src.trading.readiness.settings") as mock_settings:
        mock_settings.trading_enabled = False
        mock_settings.trading_mode = "testnet"
        mock_settings.binance_use_testnet = True
        mock_settings.binance_api_key = "k"
        mock_settings.binance_api_secret = "s"
        mock_settings.trading_dry_run = False
        with patch(
            "src.trading.readiness.get_active_execution_profile",
            return_value=(MagicMock(name="DIVAP"), MagicMock(min_confidence="high", max_open_trades=3), {"active_profile_id": "divap"}),
        ):
            with patch("src.trading.readiness.TradeRepository") as mock_repo:
                mock_repo.return_value.count_open_trades.return_value = 0
                with patch("src.trading.readiness.BinanceBroker") as mock_broker:
                    mock_broker.return_value.get_usdt_balance.return_value = __import__(
                        "decimal"
                    ).Decimal("100")
                    with patch(
                        "src.trading.readiness.build_profile_performance",
                        return_value=[],
                    ):
                        with patch("src.trading.readiness.cache_get", return_value=None):
                            with patch("src.trading.readiness.cache_set"):
                                report = build_trading_readiness()
    assert report["ready"] is False
    assert any(c["id"] == "trading_enabled" and not c["ok"] for c in report["checks"])
