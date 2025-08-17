# services/cache_decorators.py
import json
import functools
from typing import Callable, Awaitable, Any, Dict, Optional
from redis.asyncio import Redis
from services.memory_cache import memory_cache
from services.cache_stats import hit, miss

def cached(key_builder: Callable[..., str], ttl: int, namespace: str):
    """
    Usage:
    @cached(lambda user_id: user_dashboard_key(user_id), ttl=300, namespace="dashboard")
    async def build_dashboard(user_id: str, db: Database, r: Redis) -> dict:
        ...
    """
    def decorator(fn: Callable[..., Awaitable[dict]]):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            r: Redis = kwargs.get("r")
            key = key_builder(*args, **kwargs)

            # L1
            cached_l1 = await memory_cache.get(key)
            if cached_l1 is not None:
                if r: await hit(r, namespace)
                return cached_l1

            lock = await memory_cache.get_lock(key)
            async with lock:
                cached_l1 = await memory_cache.get(key)
                if cached_l1 is not None:
                    if r: await hit(r, namespace)
                    return cached_l1

                # L2
                if r:
                    cached_l2 = await r.get(key)
                    if cached_l2:
                        payload = json.loads(cached_l2)
                        await memory_cache.set(key, payload, ttl=ttl)
                        await hit(r, namespace)
                        return payload

                # Miss -> compute
                if r: await miss(r, namespace)
                data = await fn(*args, **kwargs)
                if data is not None:
                    if r:
                        await r.set(key, json.dumps(data), ex=ttl)
                    await memory_cache.set(key, data, ttl=ttl)
                return data
        return wrapper
    return decorator
