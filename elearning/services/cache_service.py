import json
import asyncio
from typing import Dict, Any
from redis.asyncio import Redis
from services.memory_cache import memory_cache
from services.cache_keys import course_key, analytics_course_key

# ---------------------------
# Invalidate course cache
# ---------------------------
async def invalidate_course_cache(r: Redis, course_id: str) -> Dict[str, Any]:
    key = course_key(course_id)
    analytics_key = analytics_course_key(course_id)

    # Parallel deletion of related keys
    await asyncio.gather(
        memory_cache.delete(key),
        memory_cache.delete(analytics_key),
        r.delete(key, analytics_key),
        memory_cache.pattern_delete("courses_list:"),
        _delete_redis_pattern(r, "courses_list:*")
    )

    return {"message": f"Cache cleared for course {course_id}"}

async def _delete_redis_pattern(r: Redis, pattern: str):
    """Efficiently delete Redis keys by pattern"""
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor=cursor, match=pattern, count=500)
        if keys:
            # Use pipeline for batch deletion
            async with r.pipeline() as pipe:
                for key in keys:
                    pipe.delete(key)
                await pipe.execute()
        if cursor == 0:
            break

# ---------------------------
# Cache Stats
# ---------------------------
async def get_cache_stats(r: Redis) -> Dict[str, Any]:
    # L1 stats
    l1_size = len(memory_cache._store)

    # L2 stats from Redis
    info = await r.info()
    redis_keys = info.get("db0", {}).get("keys", 0) if "db0" in info else 0
    memory_used = info.get("used_memory_human", "N/A")

    return {
        "memory_cache_size": l1_size,
        "redis_keys": redis_keys,
        "redis_memory_used": memory_used,
        "redis_hits": info.get("keyspace_hits"),
        "redis_misses": info.get("keyspace_misses"),
    }
