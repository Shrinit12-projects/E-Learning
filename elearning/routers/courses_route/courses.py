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
# Get analytics from existing service
from services import analytics_service

router = APIRouter(prefix="/courses", tags=["courses"])

# Route to get paginated list of courses with various filter options
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
    """
    Get paginated list of courses with filtering and sorting options.
    
    Args:
        search: Optional text to search courses
        category: Optional category filter
        tags: Optional list of tags to filter by
        difficulty: Filter by difficulty level (beginner/intermediate/advanced)
        instructor_id: Filter courses by instructor
        published: Filter by published status
        min_duration: Minimum course duration in minutes
        max_duration: Maximum course duration in minutes
        sort_by: Sort order (recent/popular/top_rated/duration)
        page: Page number for pagination
        page_size: Number of items per page
        db: MongoDB database instance
        r: Redis instance
        
    Returns:
        CoursesPage object containing paginated course results
    """
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

# Route to create a new course
@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role("instructor", "admin"))])
async def create_course(payload: CourseCreate, db: Database = Depends(get_db), r: Redis = Depends(get_redis), user=Depends(get_current_user)):
    """
    Create a new course. Only instructors and admins can create courses.
    
    Args:
        payload: CourseCreate object containing course details
        db: MongoDB database instance
        r: Redis instance
        user: Current authenticated user
        
    Returns:
        Created course object
        
    Raises:
        HTTPException: If user is not authorized or course creation fails
    """
    # enforce ownership
    print("User:", user)
    if str(payload.instructor_id) != str(user["_id"]) and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only create courses for yourself")
    doc = await course_service.create_course(db, r, payload.dict())
    print("Course created:", doc)
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to create course")
    return json.loads(JSONEncoder().encode(doc))

# Route to get a specific course by ID
@router.get("/{course_id}", response_model=CourseOut)
async def get_course(course_id: str, db: Database = Depends(get_db), r: Redis = Depends(get_redis)):
    """
    Get course details by course ID.
    
    Args:
        course_id: ID of course to retrieve
        db: MongoDB database instance
        r: Redis instance
        
    Returns:
        Course object if found
        
    Raises:
        HTTPException: If course is not found
    """
    doc = await course_service.get_course(db, r, course_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Course not found")
    return doc

# Route to update a specific module within a course
@router.put("/{course_id}/modules/{module_id}", response_model=CourseOut,
            dependencies=[Depends(require_role("instructor", "admin"))])
async def update_module(course_id: str, module_id: str, patch: ModuleUpdate,
                        db: Database = Depends(get_db), r: Redis = Depends(get_redis), user=Depends(get_current_user)):
    """
    Update a specific module within a course. Only course owner or admin can update.
    
    Args:
        course_id: ID of the course containing the module
        module_id: ID of module to update
        patch: ModuleUpdate object with fields to update
        db: MongoDB database instance
        r: Redis instance
        user: Current authenticated user
        
    Returns:
        Updated course object
        
    Raises:
        HTTPException: If course/module not found or user not authorized
    """
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

# Route to update an entire course
@router.put("/{course_id}", response_model=CourseOut,
            dependencies=[Depends(require_role("instructor", "admin"))])
async def replace_course(course_id: str, payload: CourseUpdate,
                         db: Database = Depends(get_db),
                         r: Redis = Depends(get_redis),
                         user=Depends(get_current_user)):
    """
    Update an entire course. Only course owner or admin can update.
    
    Args:
        course_id: ID of course to update
        payload: CourseUpdate object with fields to update
        db: MongoDB database instance
        r: Redis instance
        user: Current authenticated user
        
    Returns:
        Updated course object
        
    Raises:
        HTTPException: If course not found, update fails, or user not authorized
    """
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

# Route to get analytics for a course
@router.get("/{course_id}/analytics", dependencies=[Depends(require_role("instructor", "admin"))])
async def course_analytics_preview(course_id: str, db: Database = Depends(get_db), r: Redis = Depends(get_redis), user=Depends(get_current_user)):
    """
    Get analytics for a specific course. Only instructors and admins can access.
    
    Args:
        course_id: ID of course to get analytics for
        db: MongoDB database instance
        r: Redis instance
        user: Current authenticated user
        
    Returns:
        Course analytics data including enrollment, completion rates, and performance metrics
    """
    # Verify course exists and user has access
    course = await course_service.get_course(db, r, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Parse course if it's a string
    if isinstance(course, str):
        course = json.loads(course)
    
    # Enforce ownership unless admin
    if user["role"] != "admin" and course["instructor_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Not allowed")
    
    
    analytics = await analytics_service.course_performance(db, r, course_id)
    
    return analytics
