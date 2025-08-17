# tasks/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pymongo.database import Database
from redis.asyncio import Redis
from fastapi.concurrency import run_in_threadpool
import json
from repos.helper import JSONEncoder
from services.cache_keys import (
    popular_courses_key, analytics_platform_overview_key, analytics_course_key
)
from services import course_service
from repos import courses as courses_repo

def create_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler()

def schedule_jobs(scheduler: AsyncIOScheduler, db: Database, r: Redis) -> None:
    # Warm course caches periodically
    print("i am here")
    scheduler.add_job(
        warm_courses,
        trigger=IntervalTrigger(minutes=30),
        args=[db, r],
        id="warm_courses",
        replace_existing=True,
    )
    # Popular courses list (performance caching)
    scheduler.add_job(lambda: warm_popular_courses(db, r), IntervalTrigger(hours=1), id="popular_courses", replace_existing=True)
    # Platform analytics overview (analytics caching)
    scheduler.add_job(lambda: warm_platform_overview(db, r), IntervalTrigger(hours=1), id="platform_overview", replace_existing=True)
    # Example: per-course analytics (stub)
    scheduler.add_job(lambda: warm_course_analytics(db, r), IntervalTrigger(minutes=30), id="course_analytics", replace_existing=True)

async def warm_courses(db: Database, r: Redis):
    print("warming courses")
    await course_service.warm_courses_cache(db, r)

async def warm_popular_courses(db: Database, r: Redis):
    # stub: top N popular courses → attach simple counters (expand with real analytics later)
    print("warming popular courses")
    total, items = await run_in_threadpool(
        courses_repo.list_courses, db, q=None, filters={}, page=1, page_size=12, sort_by="popular"
    )
    payload = {"total": total, "items": items}
    await r.set(popular_courses_key(), json.dumps(JSONEncoder().encode(payload)), ex=60*60)

async def warm_platform_overview(db: Database, r: Redis):
    print("warming platform overview")
    # lightweight platform stats (expand later)
    total_courses = await run_in_threadpool(lambda: db.courses.count_documents({}))
    total_enroll = await run_in_threadpool(lambda: db.courses.aggregate([{"$group": {"_id": None, "sum": {"$sum": "$enroll_count"}}}]))
    total_enroll = next(total_enroll, {}).get("sum", 0)
    overview = {
        "total_courses": int(total_courses),
        "total_enrollments": int(total_enroll),
    }
    await r.set(analytics_platform_overview_key(), json.dumps(overview), ex=60*60)

async def warm_course_analytics(db: Database, r: Redis):
    print("warming course analytics")
    # stub: top N recent courses → attach simple counters (expand with real analytics later)
    total, items = await run_in_threadpool(
        courses_repo.list_courses, db, q=None, filters={}, page=1, page_size=12, sort_by="recent"
    )
    for it in items:
        cid = it.get("_id")
        if not cid: continue
        analytic = {
            "course_id": cid,
            "enroll_count": it.get("enroll_count", 0),
            "ratings_avg": it.get("ratings_avg", 0.0),
        }
        await r.set(analytics_course_key(cid), json.dumps(analytic), ex=60*15)
