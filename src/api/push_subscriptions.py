"""Web Push subscription storage (Redis)."""

from __future__ import annotations

import json

import redis

from src.core.config import settings

PUSH_SUBS_KEY = "divap:push:subscriptions"


def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def save_subscription(endpoint: str, payload: dict) -> None:
    _client().hset(PUSH_SUBS_KEY, endpoint, json.dumps(payload))


def remove_subscription(endpoint: str) -> None:
    _client().hdel(PUSH_SUBS_KEY, endpoint)


def list_subscriptions() -> list[dict]:
    raw = _client().hgetall(PUSH_SUBS_KEY)
    subs: list[dict] = []
    for value in raw.values():
        try:
            subs.append(json.loads(value))
        except json.JSONDecodeError:
            continue
    return subs
