from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from bson import ObjectId
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

def _oid(id_str: str) -> ObjectId:
    return ObjectId(id_str)

def ensure_indexes(db: Database) -> None:
    # Uniqueness per (user, course)
    db.progress.create_index([("user_id", ASCENDING), ("course_id", ASCENDING)], unique=True, name="user_course_unique")
    db.progress.create_index([("user_id", ASCENDING), ("last_accessed", DESCENDING)], name="user_last_accessed")
    db.progress.create_index([("course_id", ASCENDING)], name="by_course")

def _course_total_lessons(db: Database, course_id: str) -> int:
    doc = db.courses.find_one({"_id": _oid(course_id)}, {"lessons_count": 1})
    return int(doc.get("lessons_count", 0)) if doc else 0

def get_user_course_progress(db: Database, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
    doc = db.progress.find_one({"user_id": user_id, "course_id": course_id})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

def upsert_lesson_completion(db: Database, *, user_id: str, course_id: str, lesson_id: str, ts: datetime) -> Dict[str, Any]:
    """
    - Creates progress doc if missing
    - Adds completed lesson if not already present
    - Recomputes progress_percent with current course lessons_count
    """
    # Ensure doc exists
    try:
        db.progress.update_one(
            {"user_id": user_id, "course_id": course_id},
            {"$setOnInsert": {"completed_lessons": [], "progress_percent": 0.0, "last_accessed": ts}},
            upsert=True,
        )
    except DuplicateKeyError:
        pass

    # Add lesson if not already there
    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id, "completed_lessons.lesson_id": {"$ne": lesson_id}},
        {"$push": {"completed_lessons": {"lesson_id": lesson_id, "completed_at": ts}}, "$set": {"last_accessed": ts}}
    )
    # Always bump last_accessed (even if lesson already existed)
    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id},
        {"$set": {"last_accessed": ts}}
    )

    # Recompute percent
    prog = db.progress.find_one({"user_id": user_id, "course_id": course_id}, {"completed_lessons": 1})
    completed_count = len(prog.get("completed_lessons", [])) if prog else 0
    total_lessons = _course_total_lessons(db, course_id)
    percent = (completed_count / total_lessons * 100.0) if total_lessons > 0 else 0.0

    db.progress.update_one(
        {"user_id": user_id, "course_id": course_id},
        {"$set": {"progress_percent": percent}}
    )

    # Return full doc
    out = db.progress.find_one({"user_id": user_id, "course_id": course_id})
    out["_id"] = str(out["_id"])
    return out

def get_user_dashboard(db: Database, user_id: str) -> Dict[str, Any]:
    """
    Returns per-course progress for user, with course meta (title, slug, category)
    plus rollups for counts and averages.
    """
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$lookup": {
            "from": "courses",
            "localField": "course_id",
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
