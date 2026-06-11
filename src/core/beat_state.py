"""Redis-backed Celery beat liveness for dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import redis

from src.core.config import settings

BEAT_LAST_SEEN_KEY = "divap:beat:last_seen"
BEAT_STALE_SECONDS = 180


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def record_beat_heartbeat() -> None:
    _client().set(BEAT_LAST_SEEN_KEY, datetime.now(UTC).isoformat())


def get_beat_status() -> dict:
    raw = _client().get(BEAT_LAST_SEEN_KEY)
    last_at: datetime | None = None
    if raw:
        last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=UTC)

    seconds_since: int | None = None
    if last_at:
        seconds_since = max(0, int((datetime.now(UTC) - last_at).total_seconds()))

    active = seconds_since is not None and seconds_since <= BEAT_STALE_SECONDS

    return {
        "beat_active": active,
        "beat_last_seen_at": last_at.isoformat() if last_at else None,
        "beat_seconds_since": seconds_since,
        "beat_stale_after_seconds": BEAT_STALE_SECONDS,
    }
