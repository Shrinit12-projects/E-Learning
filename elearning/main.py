# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from config import settings
from deps import create_mongo_client, create_redis_client
from repos.users import ensure_indexes as ensure_user_indexes
from routers.health import router as health_router
from routers.user_auth import auth
from routers.courses_route import courses
from routers.student_progress import progress_route
from routers.analytics_route import analytics
from routers.cache_route import cache
from routers.realtime_route import realtime
from routers.performance_route import performance
from tasks.scheduler import create_scheduler, schedule_jobs
from services.realtime_analytics import listen_analytics_updates
from services.cache_warming import warm_critical_caches
from repos.progress import ensure_indexes as ensure_progress_indexes
from repos.users import ensure_indexes as ensure_user_indexes
import asyncio


app = FastAPI(title="E-Learning Analytics API (dev)")


@app.on_event("startup")
async def startup():
    app.state.mongo_client = create_mongo_client(settings.MONGO_URI)
    app.state.db = app.state.mongo_client.get_default_database()
    app.state.redis = create_redis_client(settings.REDIS_URL)

    # indexes
    await run_in_threadpool(ensure_user_indexes, app.state.db)
    await run_in_threadpool(ensure_progress_indexes, app.state.db)

    # APScheduler
    app.state.scheduler = create_scheduler()
    schedule_jobs(app.state.scheduler, app.state.db, app.state.redis)
    app.state.scheduler.start()
    
    # Start real-time analytics listener
    asyncio.create_task(listen_analytics_updates(app.state.redis, app.state.db))
    
    # Warm critical caches on startup
    asyncio.create_task(warm_critical_caches(app.state.db, app.state.redis))

@app.on_event("shutdown")
async def shutdown():
    try:
        app.state.mongo_client.close()
    except Exception:
        pass
    try:
        await app.state.redis.close()
    except Exception:
        pass
    try:
        app.state.scheduler.shutdown(wait=False)
    except Exception:
        pass

# Routers
app.include_router(health_router)
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(progress_route.router)
app.include_router(analytics.router)
app.include_router(cache.router)
app.include_router(realtime.router)
# Performance analysis router
app.include_router(performance.router)
