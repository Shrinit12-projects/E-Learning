from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from deps import get_redis
from auth.dependencies import require_role
from services import cache_service

router = APIRouter(prefix="/cache", tags=["cache"], dependencies=[Depends(require_role("admin"))])

@router.delete("/courses/{course_id}")
async def invalidate_course(course_id: str, r: Redis = Depends(get_redis)):
    return await cache_service.invalidate_course_cache(r, course_id)

@router.get("/stats")
async def cache_stats(r: Redis = Depends(get_redis)):
    return await cache_service.get_cache_stats(r)