import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from redis.asyncio import Redis
from pymongo.database import Database
from fastapi.concurrency import run_in_threadpool

from services.memory_cache import memory_cache
from repos import progress as repo
from repos import courses as course_repo
from repos.helper import JSONEncoder

# TTLs
PROGRESS_TTL = 60 * 5        # per-course progress cache (user scoped)
DASHBOARD_TTL = 60 * 2       # "heavily cached" per PDF

def _k_course(user_id: str, course_id: str) -> str:
    return f"progress:{user_id}:course:{course_id}"

def _k_dashboard(user_id: str) -> str:
    return f"progress:{user_id}:dashboard"

async def _get_l1(key: str) -> Optional[dict]:
    return await memory_cache.get(key)

async def _set_l1(key: str, value: dict, ttl: int) -> None:
    await memory_cache.set(key, value, ttl=ttl)

async def _del_l1(key: str) -> None:
    await memory_cache.delete(key)

async def _del_l1_prefix(prefix: str) -> None:
    await memory_cache.pattern_delete(prefix)

# ---------- Guards / helpers ----------

async def _assert_lesson_belongs_to_course(db: Database, *, course_id: str, lesson_id: str) -> None:
    course = await run_in_threadpool(course_repo.get_course_by_id, db, course_id)
    if not course:
        raise ValueError("Course not found")
    for m in course.get("modules", []):
        for l in m.get("lessons", []):
            if l.get("lesson_id") == lesson_id:
                return
    raise ValueError("Lesson not found in the specified course")

# ---------- Core ----------

async def complete_lesson(db: Database, r: Redis, *, user_id: str, course_id: str, lesson_id: str) -> Dict[str, Any]:
    # validate lesson exists
    await _assert_lesson_belongs_to_course(db, course_id=course_id, lesson_id=lesson_id)

    ts = datetime.now(timezone.utc)
    doc = await run_in_threadpool(
        repo.upsert_lesson_completion, db, user_id=user_id, course_id=course_id, lesson_id=lesson_id, ts=ts
    )

    # Invalidate caches
    ck = _k_course(user_id, course_id)
    dk = _k_dashboard(user_id)
    await _del_l1(ck); await r.delete(ck)
    await _del_l1(dk); await r.delete(dk)

    # (Optional) Seed course progress key to keep hot
    await r.set(ck, json.dumps(JSONEncoder().encode(doc)), ex=PROGRESS_TTL)
    await _set_l1(ck, doc, ttl=PROGRESS_TTL)
    return doc

async def get_course_progress(db: Database, r: Redis, *, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
    key = _k_course(user_id, course_id)

    cached = await _get_l1(key)
    if cached:
        return cached

    lock = await memory_cache.get_lock(key)
    async with lock:
        cached = await _get_l1(key)
        if cached:
            return cached

        cached_l2 = await r.get(key)
        if cached_l2:
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=PROGRESS_TTL)
            return payload

        doc = await run_in_threadpool(repo.get_user_course_progress, db, user_id, course_id)
        if doc:
            await r.set(key, json.dumps(JSONEncoder().encode(doc)), ex=PROGRESS_TTL)
            await _set_l1(key, doc, ttl=PROGRESS_TTL)
        return doc

async def get_dashboard(db: Database, r: Redis, *, user_id: str) -> Dict[str, Any]:
    key = _k_dashboard(user_id)

    cached = await _get_l1(key)
    if cached:
        return cached

    lock = await memory_cache.get_lock(key)
    async with lock:
        cached = await _get_l1(key)
        if cached:
            return cached

        cached_l2 = await r.get(key)
        if cached_l2:
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=DASHBOARD_TTL)
            return payload

        doc = await run_in_threadpool(repo.get_user_dashboard, db, user_id)
        await r.set(key, json.dumps(JSONEncoder().encode(doc)), ex=DASHBOARD_TTL)
        await _set_l1(key, doc, ttl=DASHBOARD_TTL)
        return doc
