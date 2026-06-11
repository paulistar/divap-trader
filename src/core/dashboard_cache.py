"""Redis cache for slow dashboard aggregations."""

from __future__ import annotations

import json
from typing import Any

import redis

from src.core.config import settings

MARKET_CACHE_KEY = "divap:dashboard:market"
BALANCE_CACHE_KEY = "divap:dashboard:balance"
READINESS_CACHE_KEY = "divap:dashboard:readiness"
MARKET_TTL_SECONDS = 300
BALANCE_TTL_SECONDS = 60


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def cache_get(key: str) -> dict[str, Any] | None:
    raw = _client().get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def cache_set(key: str, payload: dict[str, Any], ttl: int) -> None:
    _client().setex(key, ttl, json.dumps(payload))
