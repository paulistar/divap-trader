"""Heartbeat Redis do listener OTC Telegram — base do healthcheck/autoheal."""

from __future__ import annotations

from datetime import UTC, datetime

import redis

from src.core.config import settings

OTC_TELEGRAM_HEARTBEAT_KEY = "otc:telegram:heartbeat"
OTC_TELEGRAM_STALE_SECONDS = 120


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def record_listener_heartbeat() -> None:
    """Marca o listener como vivo agora (chamado periodicamente pelo runner)."""
    _client().set(OTC_TELEGRAM_HEARTBEAT_KEY, datetime.now(UTC).isoformat())


def listener_seconds_since_heartbeat() -> int | None:
    raw = _client().get(OTC_TELEGRAM_HEARTBEAT_KEY)
    if not raw:
        return None
    last = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - last).total_seconds()))


def listener_is_alive(stale_seconds: int = OTC_TELEGRAM_STALE_SECONDS) -> bool:
    seconds = listener_seconds_since_heartbeat()
    return seconds is not None and seconds <= stale_seconds
