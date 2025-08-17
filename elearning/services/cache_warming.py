import asyncio
from typing import List
from pymongo.database import Database
from redis.asyncio import Redis
from fastapi.concurrency import run_in_threadpool
from services import analytics_service, course_service
from repos import courses as courses_repo

async def warm_critical_caches(db: Database, r: Redis):
    """Warm most critical caches in parallel"""
    await asyncio.gather(
        analytics_service.platform_overview(db, r),
        course_service.warm_courses_cache(db, r),
        _warm_top_courses(db, r, limit=10),
        return_exceptions=True
    )

async def warm_analytics_caches(db: Database, r: Redis):
    """Warm analytics caches for active data"""
    tasks = [
        analytics_service.platform_overview(db, r),
        _warm_course_analytics_batch(db, r),
        _warm_student_patterns_batch(db, r)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

async def _warm_top_courses(db: Database, r: Redis, limit: int = 20):
    """Warm cache for top performing courses"""
    total, items = await run_in_threadpool(
        courses_repo.list_courses, db, q=None, filters={}, 
        page=1, page_size=limit, sort_by="popular"
    )
    
    tasks = []
    for item in items:
        course_id = item.get("_id")
        if course_id:
            tasks.append(analytics_service.course_performance(db, r, course_id))
    
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def _warm_course_analytics_batch(db: Database, r: Redis):
    """Batch warm course analytics"""
    await _warm_top_courses(db, r, limit=15)

async def _warm_student_patterns_batch(db: Database, r: Redis):
    """Batch warm student patterns for active users"""
    active_users = await run_in_threadpool(
        lambda: list(db.progress.distinct("user_id", {"last_accessed": {"$exists": True}}))
    )
    
    tasks = []
    for user_id in active_users[:30]:  # Top 30 active users
        tasks.append(analytics_service.student_patterns(db, r, user_id))
    
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)