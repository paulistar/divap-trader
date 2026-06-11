"""Redis-backed scan timing for dashboard."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import redis

from src.core.config import settings

SCAN_INTERVAL_SECONDS = 900
LAST_SCAN_KEY = "divap:last_scan_at"
LAST_SCAN_RESULT_KEY = "divap:last_scan_result"


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def record_scan(result: dict[str, int | list[str]]) -> None:
    client = _client()
    client.set(LAST_SCAN_KEY, datetime.now(UTC).isoformat())
    client.set(
        LAST_SCAN_RESULT_KEY,
        json.dumps(
            {
                "signals": result.get("signals", 0),
                "errors": result.get("errors", 0),
                "details": result.get("details", []),
            }
        ),
    )


def get_scan_status() -> dict:
    client = _client()
    raw = client.get(LAST_SCAN_KEY)
    result_raw = client.get(LAST_SCAN_RESULT_KEY)
    last_at: datetime | None = None
    if raw:
        last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    seconds_since: int | None = None
    seconds_until: int | None = None
    if last_at:
        elapsed = int((now - last_at).total_seconds())
        seconds_since = max(0, elapsed)
        seconds_until = max(0, SCAN_INTERVAL_SECONDS - (elapsed % SCAN_INTERVAL_SECONDS))

    last_result = json.loads(result_raw) if result_raw else {}

    return {
        "last_scan_at": last_at.isoformat() if last_at else None,
        "seconds_since_last": seconds_since,
        "seconds_until_next": seconds_until,
        "interval_seconds": SCAN_INTERVAL_SECONDS,
        "last_signals": last_result.get("signals", 0),
        "last_errors": last_result.get("errors", 0),
    }
