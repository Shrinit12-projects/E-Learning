# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
import logging
import asyncio
import sys
import os
from config import settings
from deps import create_mongo_client, create_redis_client
from logging_config import setup_logging
from middleware.error_handler import ErrorHandlerMiddleware
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


# Setup logging
log_level = "DEBUG" if settings.DEBUG else "INFO"
log_file = "logs/app.log" if settings.ENVIRONMENT == "production" else None
setup_logging(log_level=log_level, log_file=log_file)

logger = logging.getLogger(__name__)


app = FastAPI(
    title="E-Learning Analytics API",
    description="E-Learning platform with analytics and caching",
    version="1.0.0"
)


@app.on_event("startup")
async def startup():
    try:
        logger.info("Starting application...")
        
        # Database connections
        try:
            app.state.mongo_client = create_mongo_client(settings.MONGO_URI)
            app.state.db = app.state.mongo_client.get_default_database()
            logger.info("MongoDB connection established")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            sys.exit(1)
            
        try:
            app.state.redis = create_redis_client(settings.REDIS_URL)
            await app.state.redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            sys.exit(1)

        # Database indexes
        try:
            await run_in_threadpool(ensure_user_indexes, app.state.db)
            await run_in_threadpool(ensure_progress_indexes, app.state.db)
            logger.info("Database indexes ensured")
        except Exception as e:
            logger.error(f"Failed to ensure database indexes: {str(e)}")
            # Continue startup as this is not critical

        # Scheduler
        try:
            app.state.scheduler = create_scheduler()
            schedule_jobs(app.state.scheduler, app.state.db, app.state.redis)
            app.state.scheduler.start()
            logger.info("Scheduler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
            # Continue startup as this is not critical
        
        # Background tasks with error handling
        try:
            task1 = asyncio.create_task(listen_analytics_updates(app.state.redis, app.state.db))
            task1.add_done_callback(lambda t: logger.error(f"Analytics listener failed: {t.exception()}") if t.exception() else None)
            
            task2 = asyncio.create_task(warm_critical_caches(app.state.db, app.state.redis))
            task2.add_done_callback(lambda t: logger.error(f"Cache warming failed: {t.exception()}") if t.exception() else None)
            
            logger.info("Background tasks started")
        except Exception as e:
            logger.error(f"Failed to start background tasks: {str(e)}")
            # Continue startup as these are not critical
            
        logger.info("Application startup completed successfully")
        
    except Exception as e:
        logger.critical(f"Critical startup failure: {str(e)}")
        sys.exit(1)

@app.on_event("shutdown")
async def shutdown():
    logger.info("Starting application shutdown...")
    
    # Shutdown scheduler
    try:
        if hasattr(app.state, 'scheduler'):
            app.state.scheduler.shutdown(wait=False)
            logger.info("Scheduler shutdown completed")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {str(e)}")
    
    # Close Redis connection
    try:
        if hasattr(app.state, 'redis'):
            await app.state.redis.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {str(e)}")
    
    # Close MongoDB connection
    try:
        if hasattr(app.state, 'mongo_client'):
            app.state.mongo_client.close()
            logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {str(e)}")
    
    logger.info("Application shutdown completed")

# Error handling middleware (should be first)
app.add_middleware(ErrorHandlerMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(progress_route.router)
app.include_router(analytics.router)
app.include_router(cache.router)
app.include_router(realtime.router)
app.include_router(performance.router)
