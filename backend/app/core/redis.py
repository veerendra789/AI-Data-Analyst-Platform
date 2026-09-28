from __future__ import annotations

import json
import hashlib
import threading
import time
from typing import Any

import redis
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = RedisSettings()
_client: redis.Redis | None = None
_memory: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()


def client() -> redis.Redis | None:
    global _client
    if _client is None:
        try:
            candidate = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.2)
            candidate.ping()
            _client = candidate
        except redis.RedisError:
            _client = None
    return _client


def get_json(key: str) -> Any | None:
    value = client().get(key) if client() else None
    if value is None:
        with _lock:
            item = _memory.get(key)
            if not item or item[0] < time.time():
                _memory.pop(key, None)
                return None
            value = item[1]
    return json.loads(value)


def set_json(key: str, value: Any, ttl_seconds: int = 300) -> None:
    encoded = json.dumps(value, default=str)
    if client():
        client().setex(key, ttl_seconds, encoded)
    else:
        with _lock:
            _memory[key] = (time.time() + ttl_seconds, encoded)


def increment_with_expiry(key: str, ttl_seconds: int) -> int:
    redis_client = client()
    if redis_client:
        count = int(redis_client.incr(key))
        if count == 1:
            redis_client.expire(key, ttl_seconds)
        return count
    with _lock:
        now = time.time()
        expires, value = _memory.get(key, (now + ttl_seconds, "0"))
        if expires < now:
            value, expires = "0", now + ttl_seconds
        count = int(value) + 1
        _memory[key] = (expires, str(count))
        return count


def clear_memory() -> None:
    with _lock:
        _memory.clear()


def make_cache_key(scope: str, *parts: object) -> str:
    payload = json.dumps([str(part) for part in parts], separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"cache:{scope}:{digest}"


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())
