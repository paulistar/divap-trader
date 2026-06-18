"""Tests for OTC Telegram listener heartbeat (healthcheck/autoheal base)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.otc import heartbeat


def _fake_client_with_value(value: str | None) -> MagicMock:
    client = MagicMock()
    client.get.return_value = value
    return client


def test_listener_alive_when_recent() -> None:
    recent = datetime.now(UTC).isoformat()
    with patch.object(heartbeat, "_client", return_value=_fake_client_with_value(recent)):
        assert heartbeat.listener_is_alive() is True
        assert heartbeat.listener_seconds_since_heartbeat() is not None


def test_listener_dead_when_stale() -> None:
    stale = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
    with patch.object(heartbeat, "_client", return_value=_fake_client_with_value(stale)):
        assert heartbeat.listener_is_alive() is False


def test_listener_dead_when_missing() -> None:
    with patch.object(heartbeat, "_client", return_value=_fake_client_with_value(None)):
        assert heartbeat.listener_is_alive() is False
        assert heartbeat.listener_seconds_since_heartbeat() is None


def test_record_heartbeat_writes_key() -> None:
    client = MagicMock()
    with patch.object(heartbeat, "_client", return_value=client):
        heartbeat.record_listener_heartbeat()
    client.set.assert_called_once()
    key = client.set.call_args[0][0]
    assert key == heartbeat.OTC_TELEGRAM_HEARTBEAT_KEY
