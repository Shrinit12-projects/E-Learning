import json
import asyncio
from typing import Dict, Any
from redis.asyncio import Redis
from bson import ObjectId
from bson.errors import InvalidId
from services.memory_cache import memory_cache
from services.cache_keys import course_key, analytics_course_key
import logging

logger = logging.getLogger(__name__)

# ---------------------------
# Invalidate course cache
# ---------------------------
async def invalidate_course_cache(r: Redis, course_id: str) -> Dict[str, Any]:
    # Validate course_id to prevent NoSQL injection
    try:
        if not course_id or not isinstance(course_id, str):
            raise ValueError("Invalid course_id format")
        
        # Validate ObjectId format if using MongoDB ObjectIds
        ObjectId(course_id)
        
    except (InvalidId, ValueError) as e:
        logger.warning(f"Invalid course_id provided: {course_id}")
        raise ValueError(f"Invalid course_id: {str(e)}")
    
    try:
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

        logger.info(f"Cache cleared for course {course_id}")
        return {"message": f"Cache cleared for course {course_id}"}
        
    except Exception as e:
        logger.error(f"Failed to invalidate cache for course {course_id}: {str(e)}")
        raise

async def _delete_redis_pattern(r: Redis, pattern: str):
    """Efficiently delete Redis keys by pattern"""
    try:
        # Validate pattern to prevent injection
        if not pattern or not isinstance(pattern, str):
            raise ValueError("Invalid pattern")
        
        cursor = 0
        deleted_count = 0
        
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                # Use pipeline for batch deletion
                async with r.pipeline() as pipe:
                    for key in keys:
                        pipe.delete(key)
                    await pipe.execute()
                    deleted_count += len(keys)
            if cursor == 0:
                break
        
        logger.debug(f"Deleted {deleted_count} keys matching pattern: {pattern}")
        
    except Exception as e:
        logger.error(f"Failed to delete Redis pattern {pattern}: {str(e)}")
        raise

# ---------------------------
# Cache Stats
# ---------------------------
async def get_cache_stats(r: Redis) -> Dict[str, Any]:
    try:
        # L1 stats - use proper method instead of accessing private attribute
        l1_size = getattr(memory_cache, 'size', lambda: len(getattr(memory_cache, '_store', {})))()

        # L2 stats from Redis
        info = await r.info()
        redis_keys = info.get("db0", {}).get("keys", 0) if "db0" in info else 0
        memory_used = info.get("used_memory_human", "N/A")

        return {
            "memory_cache_size": l1_size,
            "redis_keys": redis_keys,
            "redis_memory_used": memory_used,
            "redis_hits": info.get("keyspace_hits", 0),
            "redis_misses": info.get("keyspace_misses", 0),
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {str(e)}")
        return {
            "memory_cache_size": 0,
            "redis_keys": 0,
            "redis_memory_used": "N/A",
            "redis_hits": 0,
            "redis_misses": 0,
            "error": "Failed to retrieve cache stats"
        }
