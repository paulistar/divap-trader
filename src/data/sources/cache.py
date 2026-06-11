import json
from typing import Any

import redis

from src.core.config import settings


class RedisCache:
    def __init__(self, url: str | None = None) -> None:
        self._client = redis.from_url(url or settings.redis_url, decode_responses=True)

    def get_json(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        self._client.setex(key, ttl_seconds, json.dumps(value))

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def candle_cache_key(self, symbol: str, timeframe: str) -> str:
        return f"candles:{symbol}:{timeframe}"
