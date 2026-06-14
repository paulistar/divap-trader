from unittest.mock import MagicMock, patch

from src.alerts.scheduler import run_divap_scan
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.execution.trade_executor import TradeExecutionResult
from datetime import UTC, datetime
from decimal import Decimal


def _signal() -> DIVAPSignal:
    return DIVAPSignal(
        symbol="BTCUSDT",
        timeframe="1h",
        direction="sell",
        confidence="medium",
        criteria=DIVAPCriteria(True, True, True, False),
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        targets=(Decimal("90"),),
        current_price=Decimal("100"),
        rsi_value=65.0,
        volume_ratio=1.5,
        divergence_type="bearish",
        pattern_detected=None,
        fibo_level=None,
        timestamp=datetime.now(UTC),
    )


def test_telegram_only_when_trade_executes() -> None:
    signal = _signal()
    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = True
    executed = TradeExecutionResult(
        trade_id=1,
        executed=True,
        reason="ok",
        symbol="BTCUSDT",
        direction="sell",
        quote_amount=Decimal("50"),
        entry_price=Decimal("100"),
        quantity=Decimal("0.5"),
    )

    with patch("src.alerts.scheduler.BinanceSource") as src_cls:
        src_cls.return_value.fetch_ohlcv.return_value = []
        with patch("src.alerts.scheduler.DIVAPScanner") as scanner_cls:
            scanner_cls.return_value.scan.return_value = signal
            with patch("src.alerts.scheduler.CandleRepository"):
                with patch("src.alerts.scheduler.AlertRepository") as alert_cls:
                    alert_cls.return_value.has_recent_alert.return_value = False
                    alert_cls.return_value.save_signal.return_value = 99
                    with patch("src.alerts.scheduler.collect_market_context", return_value=None):
                        with patch("src.alerts.scheduler.get_active_execution_profile") as prof:
                            prof.return_value = (None, MagicMock(), {"active_profile_id": "divap_ativo"})
                            with patch("src.alerts.scheduler.settings") as cfg:
                                cfg.trading_enabled = True
                                cfg.openai_api_key = ""
                                with patch("src.alerts.scheduler.TradeExecutor") as exec_cls:
                                    exec_cls.return_value.try_execute.return_value = executed
                                    with patch("src.alerts.scheduler.TelegramNotifier", return_value=mock_notifier):
                                        with patch("src.alerts.scheduler.notify_trade_opened"):
                                            run_divap_scan(
                                                symbols=("BTCUSDT",),
                                                timeframes=("1h",),
                                                notify=True,
                                            )

    mock_notifier.send.assert_called_once()
    body = mock_notifier.send.call_args[0][0]
    assert "Trade aberto" in body
    assert "BTCUSDT" in body


def test_no_telegram_when_trade_blocked() -> None:
    signal = _signal()
    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = True
    blocked = TradeExecutionResult(
        trade_id=None,
        executed=False,
        reason="confidence_below_threshold",
        symbol="BTCUSDT",
        direction="sell",
    )

    with patch("src.alerts.scheduler.BinanceSource") as src_cls:
        src_cls.return_value.fetch_ohlcv.return_value = []
        with patch("src.alerts.scheduler.DIVAPScanner") as scanner_cls:
            scanner_cls.return_value.scan.return_value = signal
            with patch("src.alerts.scheduler.CandleRepository"):
                with patch("src.alerts.scheduler.AlertRepository") as alert_cls:
                    alert_cls.return_value.has_recent_alert.return_value = False
                    alert_cls.return_value.save_signal.return_value = 99
                    with patch("src.alerts.scheduler.collect_market_context", return_value=None):
                        with patch("src.alerts.scheduler.get_active_execution_profile") as prof:
                            prof.return_value = (None, MagicMock(), {})
                            with patch("src.alerts.scheduler.settings") as cfg:
                                cfg.trading_enabled = True
                                cfg.openai_api_key = ""
                                with patch("src.alerts.scheduler.TradeExecutor") as exec_cls:
                                    exec_cls.return_value.try_execute.return_value = blocked
                                    with patch("src.alerts.scheduler.TelegramNotifier", return_value=mock_notifier):
                                        run_divap_scan(
                                            symbols=("BTCUSDT",),
                                            timeframes=("1h",),
                                            notify=True,
                                        )

    mock_notifier.send.assert_not_called()
