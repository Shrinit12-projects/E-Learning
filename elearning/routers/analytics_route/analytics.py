from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from pymongo.database import Database
from deps import get_db, get_redis
from auth.dependencies import require_role
from services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/courses/{course_id}/performance")
async def course_performance(course_id: str, db: Database = Depends(get_db), r: Redis = Depends(get_redis)):
    return await analytics_service.course_performance(db, r, course_id)

@router.get("/students/{student_id}/learning-patterns")
async def student_patterns(student_id: str, db: Database = Depends(get_db), r: Redis = Depends(get_redis)):
    return await analytics_service.student_patterns(db, r, student_id)

@router.get("/platform/overview", dependencies=[Depends(require_role("admin"))])
async def platform_overview(db: Database = Depends(get_db), r: Redis = Depends(get_redis)):
    return await analytics_service.platform_overview(db, r)
