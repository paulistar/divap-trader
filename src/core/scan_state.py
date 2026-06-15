"""Redis-backed scan timing for dashboard."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import redis

from src.core.beat_state import get_beat_status
from src.core.config import settings
from src.core.monitor_state import get_monitor_status
from src.core.scan_plan import get_active_scan_plans
from src.data.repositories.bankroll_repo import BankrollRepository

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
    plans = get_active_scan_plans()
    settings_row = BankrollRepository().get_settings()
    active_ids = list(settings_row.active_profile_ids)
    active_names = [plan.profile_name for plan in plans]

    last_at: datetime | None = None
    for plan in plans:
        raw = client.get(_profile_scan_key(plan.profile_id))
        if not raw:
            continue
        candidate = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=UTC)
        if last_at is None or candidate > last_at:
            last_at = candidate

    if last_at is None:
        raw = client.get(LAST_SCAN_KEY)
        if raw:
            last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=UTC)

    result_raw = client.get(LAST_SCAN_RESULT_KEY)
    now = datetime.now(UTC)
    seconds_since: int | None = None
    seconds_until: int | None = None
    min_interval = min(plan.interval_seconds for plan in plans) if plans else 900
    if last_at:
        elapsed = int((now - last_at).total_seconds())
        seconds_since = max(0, elapsed)
        seconds_until = max(0, min_interval - elapsed)

    last_result = json.loads(result_raw) if result_raw else {}
    primary = plans[0] if plans else None

    all_symbols: list[str] = []
    all_tfs: list[str] = []
    for plan in plans:
        for symbol in plan.symbols:
            if symbol not in all_symbols:
                all_symbols.append(symbol)
        for tf in plan.timeframes:
            if tf not in all_tfs:
                all_tfs.append(tf)

    return {
        "last_scan_at": last_at.isoformat() if last_at else None,
        "seconds_since_last": seconds_since,
        "seconds_until_next": seconds_until,
        "interval_seconds": min_interval,
        "beat_tick_seconds": BEAT_TICK_SECONDS,
        "active_profile_id": primary.profile_id if primary else active_ids[0],
        "active_profile_name": primary.profile_name if primary else "—",
        "active_profile_ids": active_ids,
        "active_profile_names": active_names,
        "scan_timeframes": all_tfs,
        "scan_symbols": all_symbols,
        "last_signals": last_result.get("signals", 0),
        "last_errors": last_result.get("errors", 0),
        "last_skipped": last_result.get("skipped", False),
        "summary": last_result.get("summary") or {},
        **get_monitor_status(),
        **get_beat_status(),
    }
