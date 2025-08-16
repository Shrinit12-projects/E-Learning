# services/memory_cache.py
"""
Simple async-friendly in-memory cache with TTL.
- Layer-1 cache for ultra-fast hot reads
- Works alongside Redis (Layer-2)
"""

import asyncio
import time
from typing import Any, Optional, Dict

class AsyncInMemoryCache:
    def __init__(self):
        self._store: Dict[str, tuple[float, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _now(self) -> float:
        return time.monotonic()

    async def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at != 0 and self._now() > expires_at:
            # expired
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 0) -> None:
        expires_at = self._now() + ttl if ttl and ttl > 0 else 0
        self._store[key] = (expires_at, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def pattern_delete(self, prefix: str) -> None:
        # simple prefix match to clear many keys
        keys = [k for k in self._store.keys() if k.startswith(prefix)]
        for k in keys:
            self._store.pop(k, None)

    async def get_lock(self, key: str) -> asyncio.Lock:
        # per-key lock for dogpile protection
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

# Singleton instance
memory_cache = AsyncInMemoryCache()
