from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from pymongo.database import Database
from typing import Optional, List
import json
from deps import get_db, get_redis
from auth.dependencies import require_role, get_current_user
from services import course_service
from schemas.course_schema import CourseCreate, CourseUpdate, ModuleUpdate, CoursesPage, CourseOut
from bson import json_util
from repos.helper import JSONEncoder

router = APIRouter(prefix="/courses", tags=["courses"])

@router.get("", response_model=CoursesPage)
async def list_courses(
    search: Optional[str] = Query(None, description="Full-text search"),
    category: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    difficulty: Optional[str] = Query(None, regex="^(beginner|intermediate|advanced)$"),
    instructor_id: Optional[str] = None,
    published: Optional[bool] = None,
    min_duration: Optional[int] = None,
    max_duration: Optional[int] = None,
    sort_by: str = Query("recent", regex="^(recent|popular|top_rated|duration)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Database = Depends(get_db),
    r: Redis = Depends(get_redis),
):
    filters = {
        **({"category": category} if category else {}),
        **({"difficulty": difficulty} if difficulty else {}),
        **({"instructor_id": instructor_id} if instructor_id else {}),
        **({"published": published} if published is not None else {}),
        **({"tags": tags} if tags else {}),
        **({"min_duration": min_duration} if min_duration is not None else {}),
        **({"max_duration": max_duration} if max_duration is not None else {}),
    }
    return await course_service.list_courses(db, r, q=search, filters=filters, page=page, page_size=page_size, sort_by=sort_by)

@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role("instructor", "admin"))])
async def create_course(payload: CourseCreate, db: Database = Depends(get_db), r: Redis = Depends(get_redis), user=Depends(get_current_user)):
    # enforce ownership
    print("User:", user)
    if str(payload.instructor_id) != str(user["_id"]) and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only create courses for yourself")
    doc = await course_service.create_course(db, r, payload.dict())
    print("Course created:", doc)
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to create course")
    return json.loads(JSONEncoder().encode(doc))

@router.get("/{course_id}", response_model=CourseOut)
async def get_course(course_id: str, db: Database = Depends(get_db), r: Redis = Depends(get_redis)):
    doc = await course_service.get_course(db, r, course_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Course not found")
    return doc

@router.put("/{course_id}/modules/{module_id}", response_model=CourseOut,
            dependencies=[Depends(require_role("instructor", "admin"))])
async def update_module(course_id: str, module_id: str, patch: ModuleUpdate,
                        db: Database = Depends(get_db), r: Redis = Depends(get_redis), user=Depends(get_current_user)):
    # optional: ensure user owns this course unless admin
    course = await course_service.get_course(db, r, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user["role"] != "admin" and course["instructor_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Not allowed")
    updated = await course_service.update_course_module(db, r, course_id, module_id, {k:v for k,v in patch.dict().items() if v is not None})
    if not updated:
        raise HTTPException(status_code=404, detail="Module not found")
    return updated

# this is for the updating the data
@router.put("/{course_id}", response_model=CourseOut,
            dependencies=[Depends(require_role("instructor", "admin"))])
async def replace_course(course_id: str, payload: CourseUpdate,
                         db: Database = Depends(get_db),
                         r: Redis = Depends(get_redis),
                         user=Depends(get_current_user)):
    # Ensure course exists
    course = await course_service.get_course(db, r, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Enforce ownership unless admin
    if user["role"] != "admin" and course["instructor_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Not allowed")

    # Perform update (only fields provided in payload)
    patch = {k: v for k, v in payload.dict().items() if v is not None}
    updated = await course_service.replace_course(db, r, course_id, patch)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update course")
    return updated

@router.get("/{course_id}/analytics", dependencies=[Depends(require_role("instructor", "admin"))])
async def course_analytics_preview(course_id: str):
    # Stub for now – will implement in Analytics section per PDF.
    # Keeping endpoint in place so links/docs remain stable.
    return {"message": "Course analytics will be implemented later"}
