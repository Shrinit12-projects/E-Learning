# services/course_service.py
import json
import hashlib
from typing import Dict, Any, Optional
from redis.asyncio import Redis
from pymongo.database import Database
from fastapi.concurrency import run_in_threadpool
from yaml import serialize
from repos import courses as repo
from services.memory_cache import memory_cache
from repos.helper import JSONEncoder
from services.cache_stats import hit, miss
from services.cache_keys import course_key, courses_list_key
from services.realtime_analytics import publish_analytics_update


# TTLs per PDF
COURSE_TTL = 60 * 5          # 5 minutes cache TTL for individual courses
COURSE_LIST_TTL = 60 * 2     # 2 minutes cache TTL for course lists

# Constants for cache warming
WARM_SORTS = ["recent", "popular", "top_rated"]  # Sort options for cache warming
WARM_PAGE_SIZE = 12  # Number of courses per page for cache warming

def _filters_key(q: Optional[str], filters: Dict[str, Any], page: int, page_size: int, sort_by: str) -> str:
    """Generate a unique cache key based on course list filter parameters."""
    # Create payload with all filter parameters
    payload = {"q": q, "filters": filters, "page": page, "page_size": page_size, "sort_by": sort_by}
    # Generate SHA1 hash of sorted JSON payload as cache key
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return digest

async def _get_l1(key: str) -> Optional[dict]:
    """Retrieve item from L1 (memory) cache."""
    return await memory_cache.get(key)

async def _set_l1(key: str, value: dict, ttl: int) -> None:
    """Store item in L1 (memory) cache with TTL."""
    await memory_cache.set(key, value, ttl=ttl)

async def _del_l1(key: str) -> None:
    """Delete item from L1 (memory) cache."""
    await memory_cache.delete(key)

async def _del_l1_prefix(prefix: str) -> None:
    """Delete all items from L1 cache matching prefix pattern."""
    await memory_cache.pattern_delete(prefix)

async def get_course(db: Database, r: Redis, course_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a course by ID using two-level caching (memory and Redis)."""
    key = course_key(course_id)

    # Try L1 cache first
    cached = await _get_l1(key)
    if cached:
        await hit(r, "courses")
        return cached

    # Use lock to prevent cache stampede
    lock = await memory_cache.get_lock(key)
    async with lock:
        # Double-check L1 cache
        cached_again = await _get_l1(key)
        if cached_again:
            await hit(r, "courses")
            return cached_again

        # Try L2 (Redis) cache
        cached_l2 = await r.get(key)
        if cached_l2:
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=COURSE_TTL)
            await hit(r, "courses")
            return payload

        # Cache miss - fetch from database
        await miss(r, "courses")
        doc = await run_in_threadpool(repo.get_course_by_id, db, course_id)
        if doc:
            # Store in both cache levels
            await r.set(key, json.dumps(doc, cls=JSONEncoder), ex=COURSE_TTL)
            await _set_l1(key, doc, ttl=COURSE_TTL)
        return doc

async def list_courses(db: Database, r: Redis, *, q: Optional[str], filters: Dict[str, Any], page: int, page_size: int, sort_by: str):
    """List courses with filtering and pagination using two-level caching."""
    digest = _filters_key(q, filters, page, page_size, sort_by)
    key = courses_list_key(digest)

    # Try L1 cache first
    cached = await _get_l1(key)
    if cached:
        await hit(r, "courses_list")
        return cached

    # Use lock to prevent cache stampede
    lock = await memory_cache.get_lock(key)
    async with lock:
        # Double-check L1 cache
        cached_again = await _get_l1(key)
        if cached_again:
            await hit(r, "courses_list")
            return cached_again

        # Try L2 (Redis) cache
        cached_l2 = await r.get(key)
        if cached_l2:
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=COURSE_LIST_TTL)
            await hit(r, "courses_list")
            return payload

        # Cache miss - fetch from database
        await miss(r, "courses_list")
        total, items = await run_in_threadpool(
            repo.list_courses, db, q=q, filters=filters, page=page, page_size=page_size, sort_by=sort_by
        )
        payload = {"total": total, "page": page, "page_size": page_size, "items": items}
        # Store in both cache levels
        await r.set(key, json.dumps(payload, cls=JSONEncoder), ex=COURSE_LIST_TTL)
        await _set_l1(key, payload, ttl=COURSE_LIST_TTL)
        return payload

async def create_course(db: Database, r: Redis, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new course and invalidate relevant caches."""
    # Insert new course
    doc = await run_in_threadpool(repo.insert_course, db, data)
    # Invalidate course lists since they're now outdated
    await _invalidate_course_lists(r)
    # Cache the new course
    key = course_key(doc["_id"])
    await r.set(key, json.dumps(doc, cls=JSONEncoder), ex=COURSE_TTL)
    await _set_l1(key, doc, ttl=COURSE_TTL)
    
    # Invalidate platform analytics cache
    from services.cache_keys import analytics_platform_overview_key
    platform_key = analytics_platform_overview_key()
    await _del_l1(platform_key)
    await r.delete(platform_key)
    
    # Publish real-time update
    await publish_analytics_update(r, "course_created", doc["_id"], {
        "course_id": doc["_id"],
        "title": doc.get("title", ""),
        "generated_at": doc.get("created_at")
    })
    
    # Also broadcast to platform overview
    await publish_analytics_update(r, "platform_update", "platform", {
        "event": "course_created",
        "course_id": doc["_id"],
        "generated_at": doc.get("created_at")
    })
    
    return doc

async def update_course_module(db: Database, r: Redis, course_id: str, module_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a course module and invalidate relevant caches."""
    # Update module in database
    doc = await run_in_threadpool(repo.update_module, db, course_id, module_id, patch)
    if doc:
        # Invalidate course caches
        key = course_key(course_id)
        await _del_l1(key); await r.delete(key)
        await _invalidate_course_lists(r)
        # Cache updated course
        await r.set(key, json.dumps(doc, cls=JSONEncoder), ex=COURSE_TTL)
        await _set_l1(key, doc, ttl=COURSE_TTL)
        
        # Publish real-time update
        await publish_analytics_update(r, "course_updated", course_id, {
            "course_id": course_id,
            "module_id": module_id,
            "generated_at": doc.get("updated_at")
        })
    return doc

async def replace_course(db: Database, r: Redis, course_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Replace an entire course and invalidate relevant caches."""
    # Replace course in database
    doc = await run_in_threadpool(repo.replace_course, db, course_id, patch)
    if doc:
        # Invalidate course caches
        key = course_key(course_id)
        await _del_l1(key); await r.delete(key)
        await _invalidate_course_lists(r)
        # Cache updated course
        await r.set(key, json.dumps(JSONEncoder().encode(doc)), ex=COURSE_TTL)
        await _set_l1(key, doc, ttl=COURSE_TTL)
    return doc

async def _invalidate_course_lists(r: Redis) -> None:
    """Invalidate all cached course lists in both cache levels."""
    # Scan and delete all course list keys from Redis
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor=cursor, match="courses_list:*", count=200)
        if keys:
            await r.delete(*keys)
        if cursor == 0:
            break
    # Clear course lists from L1 cache
    await _del_l1_prefix("courses_list:")

async def warm_courses_cache(db: Database, r: Redis) -> None:
    """Pre-warm the course cache with popular sorting options."""
    print("*** warm course cache *****")
    base_filters = {}
    q = None
    page = 1
    page_size = WARM_PAGE_SIZE
    warmed_ids = set()

    # Warm cache for each sort option
    for sort_by in WARM_SORTS:
        page_payload = await list_courses(db, r, q=q, filters=base_filters, page=page, page_size=page_size, sort_by=sort_by)
        # Collect course IDs from results
        for item in page_payload.get("items", []):
            cid = item.get("_id")
            if cid:
                warmed_ids.add(cid)
    # Warm individual course caches
    for cid in warmed_ids:
        await get_course(db, r, cid)
