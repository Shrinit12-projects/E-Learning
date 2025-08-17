# repos/progress.py  (only showing the changed/complete file for clarity)
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from services.cache_keys import analytics_course_key, user_dashboard_key, progress_key, analytics_student_patterns_key

def _oid(id_str: str) -> ObjectId:
    return ObjectId(id_str)

def ensure_indexes(db: Database) -> None:
    db.progress.create_index([("user_id", ASCENDING), ("course_id", ASCENDING)], unique=True, name="user_course_unique")
    db.progress.create_index([("user_id", ASCENDING), ("last_accessed", DESCENDING)], name="user_last_accessed")
    db.progress.create_index([("course_id", ASCENDING)], name="by_course")
    db.progress.create_index([("video_watch_times", ASCENDING)], name="video_watch_times")

def _course_total_lessons(db: Database, course_id: str) -> int:
    doc = db.courses.find_one({"_id": _oid(course_id)}, {"lessons_count": 1})
    return int(doc.get("lessons_count", 0)) if doc else 0

def get_user_course_progress(db: Database, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
    doc = db.progress.find_one({"user_id": user_id, "course_id": course_id})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

def upsert_lesson_completion(db: Database, r, *, user_id: str, course_id: str, lesson_id: str, ts: datetime) -> Dict[str, Any]:
    try:
        db.progress.update_one(
            {"user_id": user_id, "course_id": course_id},
            {"$setOnInsert": {"completed_lessons": [], "progress_percent": 0.0, "last_accessed": ts}},
            upsert=True,
        )
    except DuplicateKeyError:
        pass

    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id, "completed_lessons.lesson_id": {"$ne": lesson_id}},
        {"$push": {"completed_lessons": {"lesson_id": lesson_id, "completed_at": ts}}, "$set": {"last_accessed": ts}}
    )
    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id},
        {"$set": {"last_accessed": ts}}
    )

    prog = db.progress.find_one({"user_id": user_id, "course_id": course_id}, {"completed_lessons": 1})
    completed_count = len(prog.get("completed_lessons", [])) if prog else 0
    total_lessons = _course_total_lessons(db, course_id)
    percent = (completed_count / total_lessons * 100.0) if total_lessons > 0 else 0.0

    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id},
        {"$set": {"progress_percent": percent, "total_lessons": total_lessons}}
    )

    # Note: Cache invalidation is handled in the service layer
    
    out = db.progress.find_one({"user_id": user_id, "course_id": course_id})
    out["_id"] = str(out["_id"])
    return out

def update_video_watch_time(db: Database, user_id: str, course_id: str, lesson_id: str, watch_time: int) -> Dict[str, Any]:
    # Ensure progress document exists
    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id},
        {"$setOnInsert": {"completed_lessons": [], "progress_percent": 0.0, "video_watch_times": {}, "last_accessed": datetime.utcnow()}},
        upsert=True
    )
    
    # Update video watch time
    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id},
        {"$inc": {f"video_watch_times.{lesson_id}": watch_time}, "$set": {"last_accessed": datetime.utcnow()}}
    )
    
    out = db.progress.find_one({"user_id": user_id, "course_id": course_id})
    out["_id"] = str(out["_id"])
    return out

def get_user_dashboard(db: Database, user_id: str) -> Dict[str, Any]:
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$addFields": {"course_id_obj": {"$toObjectId": "$course_id"}}},
        {"$lookup": {
            "from": "courses",
            "localField": "course_id_obj",
            "foreignField": "_id",
            "as": "course"
        }},
        {"$unwind": "$course"},
        {"$project": {
            "_id": 0,
            "course_id": {"$toString": "$course._id"},
            "course_title": "$course.title",
            "slug": "$course.slug",
            "category": "$course.category",
            "progress_percent": "$progress_percent",
            "completed_count": {"$size": {"$ifNull": ["$completed_lessons", []]}},
            "total_lessons": "$course.lessons_count",
            "last_accessed": "$last_accessed"
        }},
        {"$sort": {"last_accessed": -1}}
    ]
    items: List[Dict[str, Any]] = list(db.progress.aggregate(pipeline))
    total_courses = len(items)
    completed_courses = sum(1 for it in items if it.get("progress_percent", 0) >= 100.0)
    avg = round(sum(it.get("progress_percent", 0) for it in items) / total_courses, 2) if total_courses else 0.0
    return {
        "user_id": user_id,
        "total_courses": total_courses,
        "completed_courses": completed_courses,
        "average_progress": avg,
        "items": items
    }
