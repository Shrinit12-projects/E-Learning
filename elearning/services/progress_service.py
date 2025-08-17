# services/progress_service.py
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from redis.asyncio import Redis
from pymongo.database import Database
from fastapi.concurrency import run_in_threadpool

from services.memory_cache import memory_cache
from repos import progress as repo
from repos import courses as course_repo
from repos.helper import JSONEncoder
from services.cache_keys import progress_key, user_dashboard_key, analytics_course_key, analytics_student_patterns_key, analytics_platform_overview_key
from services.cache_stats import hit, miss
from services.realtime_analytics import publish_analytics_update

# PDF TTLs
PROGRESS_TTL = 60 * 10       # 10 min
DASHBOARD_TTL = 60 * 5       # 5 min

async def _get_l1(key: str) -> Optional[dict]:
    return await memory_cache.get(key)

async def _set_l1(key: str, value: dict, ttl: int) -> None:
    await memory_cache.set(key, value, ttl=ttl)

async def _del_l1(key: str) -> None:
    await memory_cache.delete(key)

async def _assert_lesson_belongs_to_course(db: Database, *, course_id: str, lesson_id: str) -> None:
    course = await run_in_threadpool(course_repo.get_course_by_id, db, course_id)
    if not course:
        raise ValueError("Course not found")
    for m in course.get("modules", []):
        for l in m.get("lessons", []):
            if l.get("lesson_id") == lesson_id:
                return
    raise ValueError("Lesson not found in the specified course")

async def track_video_watch_time(db: Database, r: Redis, *, user_id: str, course_id: str, lesson_id: str, watch_time: int) -> Dict[str, Any]:
    await _assert_lesson_belongs_to_course(db, course_id=course_id, lesson_id=lesson_id)
    doc = await run_in_threadpool(repo.update_video_watch_time, db, user_id=user_id, course_id=course_id, lesson_id=lesson_id, watch_time=watch_time)
    
    # Invalidate all related caches
    ck = progress_key(user_id, course_id)
    dk = user_dashboard_key(user_id)
    ak = analytics_course_key(course_id)
    sk = analytics_student_patterns_key(user_id)
    
    # Also invalidate platform analytics cache
    pk = analytics_platform_overview_key()
    
    await asyncio.gather(
        _del_l1(ck), r.delete(ck),
        _del_l1(dk), r.delete(dk),
        _del_l1(ak), r.delete(ak),
        _del_l1(sk), r.delete(sk),
        _del_l1(pk), r.delete(pk)
    )
    
    # Publish real-time updates
    await publish_analytics_update(r, "video_watch_time", course_id, {
        "user_id": user_id,
        "lesson_id": lesson_id,
        "watch_time": watch_time,
        "generated_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Also publish platform overview update
    await publish_analytics_update(r, "platform_update", "platform", {
        "event": "video_watch_time",
        "user_id": user_id,
        "course_id": course_id,
        "lesson_id": lesson_id,
        "watch_time": watch_time,
        "generated_at": datetime.now(timezone.utc).isoformat()
    })
    
    return doc

async def complete_lesson(db: Database, r: Redis, *, user_id: str, course_id: str, lesson_id: str) -> Dict[str, Any]:
    await _assert_lesson_belongs_to_course(db, course_id=course_id, lesson_id=lesson_id)
    ts = datetime.now(timezone.utc)
    doc = await run_in_threadpool(repo.upsert_lesson_completion, db, r, user_id=user_id, course_id=course_id, lesson_id=lesson_id, ts=ts)

    # Invalidate all related caches
    ck = progress_key(user_id, course_id)
    dk = user_dashboard_key(user_id)
    ak = analytics_course_key(course_id)
    sk = analytics_student_patterns_key(user_id)
    
    # Also invalidate platform analytics cache
    pk = analytics_platform_overview_key()
    
    await asyncio.gather(
        _del_l1(ck), r.delete(ck),
        _del_l1(dk), r.delete(dk),
        _del_l1(ak), r.delete(ak),
        _del_l1(sk), r.delete(sk),
        _del_l1(pk), r.delete(pk)
    )

    # Seed progress cache hot
    serialized = json.dumps(doc, cls=JSONEncoder)
    await r.set(ck, serialized, ex=PROGRESS_TTL)
    await _set_l1(ck, json.loads(serialized), ttl=PROGRESS_TTL)
    
    # Publish real-time updates
    await publish_analytics_update(r, "lesson_completed", course_id, {
        "user_id": user_id,
        "lesson_id": lesson_id,
        "progress_percent": doc.get("progress_percent", 0),
        "generated_at": ts.isoformat()
    })
    
    # Also publish platform overview update
    await publish_analytics_update(r, "platform_update", "platform", {
        "event": "lesson_completed",
        "user_id": user_id,
        "course_id": course_id,
        "lesson_id": lesson_id,
        "generated_at": ts.isoformat()
    })
    
    return doc

async def get_course_progress(db: Database, r: Redis, *, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
    key = progress_key(user_id, course_id)

    cached = await _get_l1(key)
    if cached:
        await hit(r, "progress")
        return cached

    lock = await memory_cache.get_lock(key)
    async with lock:
        cached = await _get_l1(key)
        if cached:
            await hit(r, "progress")
            return cached

        cached_l2 = await r.get(key)
        if cached_l2:
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=PROGRESS_TTL)
            await hit(r, "progress")
            return payload

        await miss(r, "progress")
        doc = await run_in_threadpool(repo.get_user_course_progress, db, user_id, course_id)
        if doc:
            serialized = json.dumps(doc, cls=JSONEncoder)
            await r.set(key, serialized, ex=PROGRESS_TTL)
            await _set_l1(key, json.loads(serialized), ttl=PROGRESS_TTL)
        return doc

async def get_dashboard(db: Database, r: Redis, *, user_id: str) -> Dict[str, Any]:
    key = user_dashboard_key(user_id)

    cached = await _get_l1(key)
    if cached:
        print("cache hit", cached)
        await hit(r, "dashboard")
        return cached

    lock = await memory_cache.get_lock(key)
    async with lock:
        cached = await _get_l1(key)
        if cached:
            await hit(r, "dashboard")
            return cached

        cached_l2 = await r.get(key)
        if cached_l2:
            print("cache hit L2", cached_l2)
            payload = json.loads(cached_l2)
            await _set_l1(key, payload, ttl=DASHBOARD_TTL)
            await hit(r, "dashboard")
            return payload

        await miss(r, "dashboard")
        doc = await run_in_threadpool(repo.get_user_dashboard, db, user_id)

        serialized = json.dumps(doc, cls=JSONEncoder)
        print("cache miss", serialized)
        await r.set(key, serialized, ex=DASHBOARD_TTL)
        await _set_l1(key, json.loads(serialized), ttl=DASHBOARD_TTL)
        return doc
