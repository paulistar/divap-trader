"""Testes de alertas Telegram para stop win/loss OTC."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.otc.stop_alert import (
    format_otc_stop_alert,
    notify_otc_stop_if_needed,
    should_send_stop_alert,
)


def test_format_otc_stop_alert_stop_win_positive() -> None:
    at = datetime(2026, 6, 21, 14, 35, tzinfo=ZoneInfo("America/Sao_Paulo"))
    msg = format_otc_stop_alert(
        "stop_win",
        Decimal("50.25"),
        at,
        timezone="America/Sao_Paulo",
    )
    assert "Stop Win — IQ Option" in msg
    assert "POSITIVO" in msg
    assert "Valor ganho no dia" in msg
    assert "+US$ 50,25" in msg
    assert "21/06/2026 14:35" in msg


def test_format_otc_stop_alert_stop_loss_negative() -> None:
    at = datetime(2026, 6, 21, 9, 10, tzinfo=ZoneInfo("America/Sao_Paulo"))
    msg = format_otc_stop_alert(
        "stop_loss",
        Decimal("-120.5"),
        at,
        timezone="America/Sao_Paulo",
    )
    assert "Stop Loss — IQ Option" in msg
    assert "NEGATIVO" in msg
    assert "Valor perdido no dia" in msg
    assert "-US$ 120,50" in msg
    assert "21/06/2026 09:10" in msg


@patch("src.otc.stop_alert._redis_client")
def test_should_send_stop_alert_dedup(mock_redis_factory: MagicMock) -> None:
    client = MagicMock()
    mock_redis_factory.return_value = client
    client.set.side_effect = [True, None]

    assert should_send_stop_alert("2026-06-21", "stop_win") is True
    assert should_send_stop_alert("2026-06-21", "stop_win") is False


@patch("src.otc.stop_alert.should_send_stop_alert", return_value=True)
def test_notify_otc_stop_sends_telegram(mock_dedup: MagicMock) -> None:
    notifier = MagicMock()
    notifier.is_configured.return_value = True
    notifier.send.return_value = True

    sent = notify_otc_stop_if_needed(
        "stop_win",
        Decimal("75"),
        timezone="America/Sao_Paulo",
        triggered_at=datetime(2026, 6, 21, 16, 0, tzinfo=UTC),
        notifier=notifier,
    )

    assert sent is True
    notifier.send.assert_called_once()
    body = notifier.send.call_args.args[0]
    assert "POSITIVO" in body
    assert "+US$ 75,00" in body


@patch("src.otc.stop_alert.should_send_stop_alert", return_value=False)
def test_notify_otc_stop_skips_when_already_sent(mock_dedup: MagicMock) -> None:
    notifier = MagicMock()
    assert notify_otc_stop_if_needed("stop_loss", Decimal("-10"), notifier=notifier) is False
    notifier.send.assert_not_called()
