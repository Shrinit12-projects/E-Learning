# tasks/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pymongo.database import Database
from redis.asyncio import Redis
from fastapi.concurrency import run_in_threadpool
import json
from repos.helper import JSONEncoder
from services.cache_keys import (
    popular_courses_key
)
from services import course_service, analytics_service, cache_warming
from repos import courses as courses_repo

def create_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler()

def schedule_jobs(scheduler: AsyncIOScheduler, db: Database, r: Redis) -> None:
    from .backup_tasks import schedule_backup_jobs
    
    # Schedule backup jobs
    schedule_backup_jobs(scheduler, db, r)
    
    # Critical caches (high frequency)
    scheduler.add_job(
        cache_warming.warm_critical_caches,
        trigger=IntervalTrigger(minutes=5),
        args=[db, r],
        id="critical_caches",
        replace_existing=True,
    )

    # Analytics caches (medium frequency)
    scheduler.add_job(
        cache_warming.warm_analytics_caches,
        trigger=IntervalTrigger(minutes=30),
        args=[db, r],
        id="analytics_caches",
        replace_existing=True,
    )

    # Popular courses list
    scheduler.add_job(
        warm_popular_courses,
        trigger=IntervalTrigger(hours=1),
        args=[db, r],
        id="popular_courses",
        replace_existing=True,
    )

async def warm_popular_courses(db: Database, r: Redis):
    print("warming popular courses")
    total, items = await run_in_threadpool(
        courses_repo.list_courses, db, q=None, filters={}, page=1, page_size=12, sort_by="popular"
    )
    payload = {"total": total, "items": items}
    await r.set(popular_courses_key(), json.dumps(JSONEncoder().encode(payload)), ex=60*60)
