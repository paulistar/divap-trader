"""Redis-backed scan timing for dashboard."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import redis

from src.core.beat_state import get_beat_status
from src.core.config import settings
from src.core.scan_plan import get_active_scan_plan

BEAT_TICK_SECONDS = 300
LAST_SCAN_KEY = "divap:last_scan_at"
LAST_SCAN_PROFILE_KEY = "divap:last_scan_profile_id"
LAST_SCAN_RESULT_KEY = "divap:last_scan_result"
PROFILE_SCAN_KEY_PREFIX = "divap:last_scan_at:"


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _profile_scan_key(profile_id: str) -> str:
    return f"{PROFILE_SCAN_KEY_PREFIX}{profile_id}"


def record_scan(profile_id: str, result: dict[str, int | list[str] | dict]) -> None:
    client = _client()
    now = datetime.now(UTC).isoformat()
    client.set(LAST_SCAN_KEY, now)
    client.set(LAST_SCAN_PROFILE_KEY, profile_id)
    client.set(_profile_scan_key(profile_id), now)
    client.set(
        LAST_SCAN_RESULT_KEY,
        json.dumps(
            {
                "profile_id": profile_id,
                "signals": result.get("signals", 0),
                "errors": result.get("errors", 0),
                "details": result.get("details", []),
                "summary": result.get("summary", {}),
                "skipped": result.get("skipped", False),
            }
        ),
    )


def get_last_scan_at(profile_id: str) -> datetime | None:
    raw = _client().get(_profile_scan_key(profile_id))
    if not raw:
        return None
    last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=UTC)
    return last_at


def get_scan_status() -> dict:
    client = _client()
    plan = get_active_scan_plan()
    raw = client.get(_profile_scan_key(plan.profile_id)) or client.get(LAST_SCAN_KEY)
    result_raw = client.get(LAST_SCAN_RESULT_KEY)
    last_at: datetime | None = None
    if raw:
        last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    seconds_since: int | None = None
    seconds_until: int | None = None
    interval = plan.interval_seconds
    if last_at:
        elapsed = int((now - last_at).total_seconds())
        seconds_since = max(0, elapsed)
        seconds_until = max(0, interval - elapsed)

    last_result = json.loads(result_raw) if result_raw else {}

    return {
        "last_scan_at": last_at.isoformat() if last_at else None,
        "seconds_since_last": seconds_since,
        "seconds_until_next": seconds_until,
        "interval_seconds": interval,
        "beat_tick_seconds": BEAT_TICK_SECONDS,
        "active_profile_id": plan.profile_id,
        "active_profile_name": plan.profile_name,
        "scan_timeframes": list(plan.timeframes),
        "scan_symbols": list(plan.symbols),
        "last_signals": last_result.get("signals", 0),
        "last_errors": last_result.get("errors", 0),
        "last_skipped": last_result.get("skipped", False),
        "summary": last_result.get("summary") or {},
        **get_beat_status(),
    }
