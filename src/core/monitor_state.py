"""Redis-backed position monitor timing for dashboard."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import redis

from src.core.config import settings
from src.core.scan_plan import get_active_scan_plan, should_run_interval

MONITOR_BEAT_TICK_SECONDS = 60
PROFILE_MONITOR_KEY_PREFIX = "divap:last_monitor_at:"
LAST_MONITOR_RESULT_KEY = "divap:last_monitor_result"


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _profile_monitor_key(profile_id: str) -> str:
    return f"{PROFILE_MONITOR_KEY_PREFIX}{profile_id}"


def record_monitor(profile_id: str, result: dict[str, int | bool | str]) -> None:
    client = _client()
    now = datetime.now(UTC).isoformat()
    client.set(_profile_monitor_key(profile_id), now)
    client.set(
        LAST_MONITOR_RESULT_KEY,
        json.dumps(
            {
                "profile_id": profile_id,
                "checked": result.get("checked", 0),
                "closed": result.get("closed", 0),
                "errors": result.get("errors", 0),
                "skipped": result.get("skipped", False),
            }
        ),
    )


def get_last_monitor_at(profile_id: str) -> datetime | None:
    raw = _client().get(_profile_monitor_key(profile_id))
    if not raw:
        return None
    last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=UTC)
    return last_at


def should_run_monitor(profile_id: str | None = None) -> bool:
    plan = get_active_scan_plan()
    pid = profile_id or plan.profile_id
    return should_run_interval(
        plan.monitor_interval_seconds,
        get_last_monitor_at(pid),
    )


def get_monitor_status() -> dict:
    plan = get_active_scan_plan()
    raw = _client().get(_profile_monitor_key(plan.profile_id))
    result_raw = _client().get(LAST_MONITOR_RESULT_KEY)
    last_at: datetime | None = None
    if raw:
        last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    seconds_since: int | None = None
    seconds_until: int | None = None
    interval = plan.monitor_interval_seconds
    if last_at:
        elapsed = int((now - last_at).total_seconds())
        seconds_since = max(0, elapsed)
        seconds_until = max(0, interval - elapsed)

    last_result = json.loads(result_raw) if result_raw else {}

    return {
        "last_monitor_at": last_at.isoformat() if last_at else None,
        "seconds_since_last_monitor": seconds_since,
        "seconds_until_next_monitor": seconds_until,
        "monitor_interval_seconds": interval,
        "monitor_beat_tick_seconds": MONITOR_BEAT_TICK_SECONDS,
        "last_monitor_checked": last_result.get("checked", 0),
        "last_monitor_closed": last_result.get("closed", 0),
        "last_monitor_skipped": last_result.get("skipped", False),
    }
