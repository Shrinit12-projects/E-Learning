# services/cache_stats.py
from typing import Dict, Any
from redis.asyncio import Redis

HITS_HASH = "cache_stats:hits"
MISSES_HASH = "cache_stats:misses"

async def hit(r: Redis, namespace: str) -> None:
    await r.hincrby(HITS_HASH, namespace, 1)

async def miss(r: Redis, namespace: str) -> None:
    await r.hincrby(MISSES_HASH, namespace, 1)

async def get_stats(r: Redis) -> Dict[str, Any]:
    hits = await r.hgetall(HITS_HASH) or {}
    misses = await r.hgetall(MISSES_HASH) or {}
    # convert str->int
    hits = {k:int(v) for k,v in hits.items()}
    misses = {k:int(v) for k,v in misses.items()}
    totals = {
        "hits": sum(hits.values()),
        "misses": sum(misses.values()),
        "hit_ratio": round((sum(hits.values()) / max(1, (sum(hits.values()) + sum(misses.values())))) * 100, 2)
    }
    return {"hits": hits, "misses": misses, "totals": totals}
