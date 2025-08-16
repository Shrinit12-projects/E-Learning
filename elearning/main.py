# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from config import settings
from deps import create_mongo_client, create_redis_client
from repos.users import ensure_indexes as ensure_user_indexes
from repos.courses import ensure_indexes as ensure_course_indexes
from routers.health import router as health_router
from routers.user_auth import auth
from routers.courses_route import courses
from services.course_service import warm_courses_cache  # NEW
from repos.progress import ensure_indexes as ensure_progress_indexes
from routers.student_progress import progress_route



app = FastAPI(title="E-Learning Analytics API (dev)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    # Mongo
    app.state.mongo_client = create_mongo_client(settings.MONGO_URI)
    app.state.db = app.state.mongo_client.get_default_database()
    # Redis
    app.state.redis = create_redis_client(settings.REDIS_URL)

    # Indexes (blocking -> threadpool)
    await run_in_threadpool(ensure_user_indexes, app.state.db)
    await run_in_threadpool(ensure_course_indexes, app.state.db)
    await run_in_threadpool(ensure_progress_indexes, app.state.db)

    # ---- Cache Warming ----
    # Warm popular/recent lists + first-page results + individual courses referenced
    try:
        await warm_courses_cache(app.state.db, app.state.redis)
    except Exception:
        # Warming failures must never block startup
        pass

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

# Routers
app.include_router(health_router)
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(progress_route.router)
