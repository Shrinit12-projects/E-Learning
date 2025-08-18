from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from deps import get_redis, get_db
from redis.asyncio import Redis
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"], prefix="/api/v1")

@router.get("/health", summary="Health Check", description="Check the health status of the application and its dependencies")
async def health_check(r: Redis = Depends(get_redis), db: Database = Depends(get_db)):
    redis_status = "disconnected"
    mongo_status = "disconnected"
    redis_error = None
    mongo_error = None
    
    # Test Redis connection
    try:
        await r.ping()
        redis_status = "connected"
    except ConnectionError as e:
        logger.warning(f"Redis connection failed: {str(e)}")
        redis_error = "Connection failed"
    except Exception as e:
        logger.error(f"Redis health check error: {str(e)}")
        redis_error = "Health check failed"
    
    # Test MongoDB connection
    try:
        db.command("ping")
        mongo_status = "connected"
    except ConnectionError as e:
        logger.warning(f"MongoDB connection failed: {str(e)}")
        mongo_error = "Connection failed"
    except Exception as e:
        logger.error(f"MongoDB health check error: {str(e)}")
        mongo_error = "Health check failed"
    
    # Determine overall status
    if redis_status == "connected" and mongo_status == "connected":
        overall_status = "healthy"
    elif redis_status == "connected" or mongo_status == "connected":
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    response = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "redis": {
                "status": redis_status,
                "error": redis_error
            },
            "mongodb": {
                "status": mongo_status,
                "error": mongo_error
            }
        }
    }
    
    # Return appropriate HTTP status
    if overall_status == "unhealthy":
        raise HTTPException(status_code=503, detail=response)
    
    return response