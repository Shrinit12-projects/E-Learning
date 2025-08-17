# routers/progress_router.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from redis.asyncio import Redis
from pymongo.database import Database

from deps import get_db, get_redis
from auth.dependencies import get_current_user
from services import progress_service
from schemas.progress_schema import CompleteLessonIn, CourseProgressOut, ProgressDashboardOut, VideoWatchTimeIn

router = APIRouter(prefix="/progress", tags=["progress"])

@router.post("/video-watch-time", status_code=status.HTTP_204_NO_CONTENT)
async def track_video_watch_time(payload: VideoWatchTimeIn,
                                db: Database = Depends(get_db),
                                r: Redis = Depends(get_redis),
                                user = Depends(get_current_user)):
    try:
        await progress_service.track_video_watch_time(
            db, r, user_id=str(user["_id"]), 
            course_id=payload.course_id, 
            lesson_id=payload.lesson_id, 
            watch_time=payload.watch_time
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

@router.post("/lessons/{lesson_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
async def complete_lesson(lesson_id: str,
                          payload: CompleteLessonIn,
                          background: BackgroundTasks,
                          db: Database = Depends(get_db),
                          r: Redis = Depends(get_redis),
                          user = Depends(get_current_user)):
    try:
        await progress_service.complete_lesson(
            db, r, user_id=str(user["_id"]), course_id=payload.course_id, lesson_id=lesson_id
        )
        # Warm the dashboard asynchronously (post-write)
        background.add_task(progress_service.get_dashboard, db, r, user_id=str(user["_id"]))
        return
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

@router.get("/courses/{course_id}", response_model=CourseProgressOut)
async def course_progress(course_id: str,
                          db: Database = Depends(get_db),
                          r: Redis = Depends(get_redis),
                          user = Depends(get_current_user)):
    doc = await progress_service.get_course_progress(db, r, user_id=str(user["_id"]), course_id=course_id)
    if not doc:
        return {
            "user_id": str(user["_id"]),
            "course_id": course_id,
            "progress_percent": 0.0,
            "completed_count": 0,
            "total_lessons": 0,
            "completed_lessons": [],
            "last_accessed": None
        }
    return {
        "user_id": doc["user_id"],
        "course_id": doc["course_id"],
        "progress_percent": doc.get("progress_percent", 0.0),
        "completed_count": len(doc.get("completed_lessons", [])),
        "total_lessons": doc.get("total_lessons", 0),
        "completed_lessons": doc.get("completed_lessons", []),
        "video_watch_times": doc.get("video_watch_times", {}),
        "last_accessed": doc.get("last_accessed")
    }

@router.get("/dashboard", response_model=ProgressDashboardOut)
async def progress_dashboard(db: Database = Depends(get_db),
                             r: Redis = Depends(get_redis),
                             user = Depends(get_current_user)):
    doc = await progress_service.get_dashboard(db, r, user_id=str(user["_id"]))
    doc.setdefault("user_id", str(user["_id"]))
    doc.setdefault("items", [])
    doc.setdefault("total_courses", 0)
    doc.setdefault("completed_courses", 0)
    doc.setdefault("average_progress", 0.0)
    return doc
