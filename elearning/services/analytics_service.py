import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from pymongo.database import Database
from redis.asyncio import Redis
from fastapi.concurrency import run_in_threadpool
from services.memory_cache import memory_cache
from services.cache_keys import analytics_course_key, analytics_platform_overview_key, analytics_student_patterns_key
from bson import ObjectId

# TTLs - Optimized based on data volatility
COURSE_ANALYTICS_TTL = 60 * 10      # 10 min (more volatile)
STUDENT_ANALYTICS_TTL = 60 * 20     # 20 min 
PLATFORM_ANALYTICS_TTL = 60 * 45    # 45 min (less volatile)

# ---------------------------
# Helper
# ---------------------------
async def _get_cache(r: Redis, key: str, ttl: int) -> Optional[dict]:
    # L1 cache check
    cached = await memory_cache.get(key)
    if cached:
        return cached

    # L2 cache check with pipeline
    async with r.pipeline() as pipe:
        await pipe.get(key)
        results = await pipe.execute()
        cached_l2 = results[0]
    
    if cached_l2:
        try:
            payload = json.loads(cached_l2)
            # Async set to L1 without blocking
            await memory_cache.set(key, payload, ttl=ttl//2)  # Shorter L1 TTL
            return payload
        except json.JSONDecodeError:
            await r.delete(key)  # Clean corrupted data
    return None

async def _set_cache(r: Redis, key: str, value: dict, ttl: int):
    # Parallel cache setting
    serialized = json.dumps(value)
    await asyncio.gather(
        r.set(key, serialized, ex=ttl),
        memory_cache.set(key, value, ttl=ttl//2)
    )

# ---------------------------
# Course Performance
# ---------------------------
async def course_performance(db: Database, r: Redis, course_id: str) -> Dict[str, Any]:
    key = analytics_course_key(course_id)

    cached = await _get_cache(r, key, COURSE_ANALYTICS_TTL)
    if cached:
        return cached

    # Compute from DB (aggregation pipeline)
    pipeline = [
        {"$match": {"course_id": course_id}},
        {"$group": {
            "_id": "$course_id",
            "students": {"$addToSet": "$user_id"},
            "avg_completion": {"$avg": "$progress_percent"},
            "total_watch_time": {"$sum": {"$sum": {"$map": {"input": {"$objectToArray": {"$ifNull": ["$video_watch_times", {}]}}, "as": "item", "in": "$$item.v"}}}},
            "avg_quiz_score": {"$avg": 0},
        }}
    ]
    result = list(db.progress.aggregate(pipeline))
    if not result:
        return {"course_id": course_id, "students": 0, "avg_completion": 0, "total_watch_time": 0, "avg_quiz_score": 0}

    doc = result[0]
    students_count = len(doc.get("students", []))
    total_watch_time = doc.get("total_watch_time", 0)
    
    payload = {
        "course_id": course_id,
        "students": students_count,
        "avg_completion": round(doc.get("avg_completion") or 0, 2),
        "total_watch_time_minutes": round(total_watch_time / 60, 2),
        "avg_watch_time_per_student": round((total_watch_time / students_count / 60), 2) if students_count > 0 else 0,
        "avg_quiz_score": round(doc.get("avg_quiz_score") or 0, 2),
        "generated_at": datetime.utcnow().isoformat()
    }

    await _set_cache(r, key, payload, COURSE_ANALYTICS_TTL)
    return payload

# ---------------------------
# Student Learning Patterns
# ---------------------------
async def student_patterns(db: Database, r: Redis, user_id: str) -> Dict[str, Any]:
    key = analytics_student_patterns_key(user_id)

    cached = await _get_cache(r, key, STUDENT_ANALYTICS_TTL)
    if cached:
        return cached

    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$user_id",
            "avg_completion": {"$avg": "$progress_percent"},
            "total_courses": {"$sum": 1},
            "total_watch_time": {"$sum": {"$sum": {"$map": {"input": {"$objectToArray": {"$ifNull": ["$video_watch_times", {}]}}, "as": "item", "in": "$$item.v"}}}},
            "active_days": {"$addToSet": {"$dateToString": {"format": "%Y-%m-%d", "date": "$last_accessed"}}}
        }}
    ]
    result = list(db.progress.aggregate(pipeline))
    if not result:
        return {"user_id": user_id, "avg_completion": 0, "total_courses": 0, "total_watch_time_minutes": 0, "active_days": 0}

    doc = result[0]
    total_courses = doc.get("total_courses", 0)
    total_watch_time = doc.get("total_watch_time", 0)
    
    payload = {
        "user_id": user_id,
        "avg_completion": round(doc.get("avg_completion") or 0, 2),
        "total_courses": total_courses,
        "total_watch_time_minutes": round(total_watch_time / 60, 2),
        "avg_watch_time_per_course": round((total_watch_time / total_courses / 60), 2) if total_courses > 0 else 0,
        "active_days": len(doc.get("active_days", [])),
        "generated_at": datetime.utcnow().isoformat()
    }

    await _set_cache(r, key, payload, STUDENT_ANALYTICS_TTL)
    return payload

# ---------------------------
# Platform Overview
# ---------------------------
async def platform_overview(db: Database, r: Redis) -> Dict[str, Any]:
    key = analytics_platform_overview_key()

    cached = await _get_cache(r, key, PLATFORM_ANALYTICS_TTL)
    if cached:
        return cached

    # Aggregates: total courses, active users, avg ratings, popular categories
    courses_count = db.courses.count_documents({})
    students_count = db.progress.distinct("user_id")
    avg_rating_doc = list(db.courses.aggregate([{"$group": {"_id": None, "avg_rating": {"$avg": "$ratings_avg"}}}]))
    categories_doc = list(db.courses.aggregate([{"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 5}]))

    payload = {
        "total_courses": courses_count,
        "active_students": len(students_count),
        "avg_rating": round(avg_rating_doc[0]["avg_rating"], 2) if avg_rating_doc else 0,
        "popular_categories": categories_doc,
        "generated_at": datetime.utcnow().isoformat()
    }

    await _set_cache(r, key, payload, PLATFORM_ANALYTICS_TTL)
    return payload
