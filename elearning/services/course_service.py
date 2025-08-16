# services/course_service.py
import json
import hashlib
from typing import Dict, Any, Optional
from redis.asyncio import Redis
from pymongo.database import Database
from fastapi.concurrency import run_in_threadpool
from repos import courses as repo
from services.memory_cache import memory_cache
from repos.helper import JSONEncoder

# TTLs (seconds)
COURSE_TTL = 60 * 5         # 5 minutes
COURSE_LIST_TTL = 60 * 5    # 5 minutes

# Warming settings
WARM_TOP_N = 12
WARM_SORTS = ["recent", "popular", "top_rated"]
WARM_PAGE_SIZE = 12


# ---------------------------
# Cache utils
# ---------------------------

def _filters_key(q: Optional[str], filters: Dict[str, Any], page: int, page_size: int, sort_by: str) -> str:
    payload = {"q": q, "filters": filters, "page": page, "page_size": page_size, "sort_by": sort_by}
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"courses_list:{digest}"

async def _get_l1(key: str) -> Optional[dict]:
    return await memory_cache.get(key)

async def _set_l1(key: str, value: dict, ttl: int) -> None:
    await memory_cache.set(key, value, ttl=ttl)

async def _del_l1(key: str) -> None:
    await memory_cache.delete(key)

async def _del_l1_prefix(prefix: str) -> None:
    await memory_cache.pattern_delete(prefix)


# ---------------------------
# Core services
# ---------------------------

async def get_course(db: Database, r: Redis, course_id: str) -> Optional[Dict[str, Any]]:
    """
    Multi-level cache read order:
      1) L1: in-memory
      2) L2: Redis
      3) DB -> set L2 -> set L1
    """
    key = f"course:{course_id}"

    # L1 check
    cached = await _get_l1(key)
    if cached:
        return cached

    lock = await memory_cache.get_lock(key)
    async with lock:
        cached_again = await _get_l1(key)
        if cached_again:
            return cached_again

        # L2
        cached_l2 = await r.get(key)
        if cached_l2:
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=COURSE_TTL)
            return payload

        # DB
        doc = await run_in_threadpool(repo.get_course_by_id, db, course_id)
        if doc:
            await r.set(key, json.dumps(JSONEncoder().encode(doc)), ex=COURSE_TTL)
            await _set_l1(key, doc, ttl=COURSE_TTL)
        return doc


async def list_courses(
    db: Database, r: Redis, *, q: Optional[str], filters: Dict[str, Any], page: int, page_size: int, sort_by: str
):
    key = _filters_key(q, filters, page, page_size, sort_by)

    # L1
    cached = await _get_l1(key)
    if cached:
        return cached

    lock = await memory_cache.get_lock(key)
    async with lock:
        cached_again = await _get_l1(key)
        if cached_again:
            return cached_again

        # L2
        cached_l2 = await r.get(key)
        if cached_l2:
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=COURSE_LIST_TTL)
            return payload

        # DB
        total, items = await run_in_threadpool(
            repo.list_courses, db, q=q, filters=filters, page=page, page_size=page_size, sort_by=sort_by
        )
        payload = {"total": total, "page": page, "page_size": page_size, "items": items}
        await r.set(key, json.dumps(JSONEncoder().encode(payload)), ex=COURSE_LIST_TTL)
        await _set_l1(key, payload, ttl=COURSE_LIST_TTL)
        return payload


async def create_course(db: Database, r: Redis, data: Dict[str, Any]) -> Dict[str, Any]:
    doc = await run_in_threadpool(repo.insert_course, db, data)

    # invalidate lists
    await _invalidate_course_lists(r)

    # seed single-course cache
    key = f"course:{doc['_id']}"
    await r.set(key, json.dumps(JSONEncoder().encode(doc)), ex=COURSE_TTL)
    await _set_l1(key, doc, ttl=COURSE_TTL)
    return doc


async def update_course_module(db: Database, r: Redis, course_id: str, module_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    doc = await run_in_threadpool(repo.update_module, db, course_id, module_id, patch)
    if doc:
        key = f"course:{course_id}"
        await _del_l1(key)
        await r.delete(key)
        await _invalidate_course_lists(r)
        await r.set(key, json.dumps(JSONEncoder().encode(doc)), ex=COURSE_TTL)
        await _set_l1(key, doc, ttl=COURSE_TTL)
    return doc


async def replace_course(db: Database, r: Redis, course_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    doc = await run_in_threadpool(repo.replace_course, db, course_id, patch)
    if doc:
        key = f"course:{course_id}"
        await _del_l1(key)
        await r.delete(key)
        await _invalidate_course_lists(r)
        await r.set(key, json.dumps(JSONEncoder().encode(doc)), ex=COURSE_TTL)
        await _set_l1(key, doc, ttl=COURSE_TTL)
    return doc


# ---------------------------
# Cache Invalidation + Warming
# ---------------------------

async def _invalidate_course_lists(r: Redis) -> None:
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor=cursor, match="courses_list:*", count=200)
        if keys:
            await r.delete(*keys)
        if cursor == 0:
            break
    await _del_l1_prefix("courses_list:")


async def warm_courses_cache(db: Database, r: Redis) -> None:
    base_filters = {}
    q = None
    page = 1
    page_size = WARM_PAGE_SIZE
    warmed_ids = set()

    for sort_by in WARM_SORTS:
        page_payload = await list_courses(
            db, r, q=q, filters=base_filters, page=page, page_size=page_size, sort_by=sort_by
        )
        for item in page_payload.get("items", []):
            cid = item.get("_id")
            if cid:
                warmed_ids.add(cid)

    for cid in warmed_ids:
        await get_course(db, r, cid)
