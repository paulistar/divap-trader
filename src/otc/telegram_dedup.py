from __future__ import annotations

import redis

from src.core.config import settings

DEDUP_TTL_SECONDS = 86_400


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _dedup_key(chat_id: str, message_id: int) -> str:
    return f"otc:telegram:msg:{chat_id}:{message_id}"


def is_duplicate_message(chat_id: str, message_id: int) -> bool:
    client = _redis_client()
    key = _dedup_key(chat_id, message_id)
    created = client.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS)
    return created is None
