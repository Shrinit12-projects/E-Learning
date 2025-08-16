from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING, TEXT
from bson import ObjectId
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import uuid

# ---------------------------
# Helpers
# ---------------------------

def _to_object_id(id_str: str) -> ObjectId:
    return ObjectId(id_str)

def _denormalize(course: Dict[str, Any]) -> Dict[str, Any]:
    lessons = 0
    duration = 0
    for m in course.get("modules", []):
        for l in m.get("lessons", []):
            lessons += 1
            duration += int(l.get("duration_minutes", 0))
    course["lessons_count"] = lessons
    course["total_duration_minutes"] = duration
    return course

# ---------------------------
# Indexes
# ---------------------------

def ensure_indexes(db: Database) -> None:
    db.courses.create_index(
        [("title", TEXT), ("description", TEXT), ("tags", TEXT)],
        name="courses_text"
    )
    db.courses.create_index([("category", ASCENDING), ("published", ASCENDING), ("difficulty", ASCENDING)])
    db.courses.create_index([("instructor_id", ASCENDING), ("created_at", DESCENDING)])
    db.courses.create_index([("slug", ASCENDING)], unique=True, sparse=True)

# ---------------------------
# CRUD
# ---------------------------

def insert_course(db: Database, data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    for m in data.get("modules", []):
        m["module_id"] = m.get("module_id") or str(uuid.uuid4())
        for l in m.get("lessons", []):
            l["lesson_id"] = l.get("lesson_id") or str(uuid.uuid4())

    data = _denormalize({
        **data,
        "instructor_id": str(data["instructor_id"]),
        "ratings_avg": 0.0,
        "ratings_count": 0,
        "enroll_count": 0,
        "created_at": now,
        "updated_at": now,
    })

    result = db.courses.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data

def get_course_by_id(db: Database, course_id: str) -> Optional[Dict[str, Any]]:
    doc = db.courses.find_one({"_id": _to_object_id(course_id)})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

def replace_course(db: Database, course_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # make sure counters stay correct if modules/lessons are updated
    patch = _denormalize(patch)
    patch["updated_at"] = datetime.utcnow()
    db.courses.update_one({"_id": _to_object_id(course_id)}, {"$set": patch})
    return get_course_by_id(db, course_id)

def update_module(db: Database, course_id: str, module_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    set_ops = {f"modules.$.{k}": v for k, v in patch.items() if k in ("title", "index", "lessons")}
    set_ops["updated_at"] = datetime.utcnow()
    res = db.courses.update_one(
        {"_id": _to_object_id(course_id), "modules.module_id": module_id},
        {"$set": set_ops}
    )
    if res.matched_count == 0:
        return None

    # re-denormalize counters after update
    doc = db.courses.find_one({"_id": _to_object_id(course_id)})
    if not doc:
        return None
    doc = _denormalize(doc)
    db.courses.update_one({"_id": _to_object_id(course_id)}, {"$set": {
        "lessons_count": doc["lessons_count"],
        "total_duration_minutes": doc["total_duration_minutes"],
        "updated_at": datetime.utcnow()
    }})
    return get_course_by_id(db, course_id)

# ---------------------------
# Query helpers
# ---------------------------

def _build_match(filters: Dict[str, Any]) -> Dict[str, Any]:
    match: Dict[str, Any] = {}
    if "published" in filters:
        match["published"] = filters["published"]
    if "category" in filters:
        match["category"] = filters["category"]
    if "difficulty" in filters:
        match["difficulty"] = filters["difficulty"]
    if "instructor_id" in filters:
        match["instructor_id"] = str(filters["instructor_id"])
    if "tags" in filters and filters["tags"]:
        match["tags"] = {"$all": filters["tags"]}
    if "min_duration" in filters or "max_duration" in filters:
        rng = {}
        if "min_duration" in filters: rng["$gte"] = int(filters["min_duration"])
        if "max_duration" in filters: rng["$lte"] = int(filters["max_duration"])
        match["total_duration_minutes"] = rng
    return match

# ---------------------------
# List with search + filters
# ---------------------------

def list_courses(
    db: Database,
    *,
    q: Optional[str],
    filters: Dict[str, Any],
    page: int,
    page_size: int,
    sort_by: str
) -> Tuple[int, List[Dict[str, Any]]]:
    match = _build_match(filters)

    pipeline: List[Dict[str, Any]] = []
    if q:
        pipeline.append({"$match": {**match, "$text": {"$search": q}}})
        pipeline.append({"$addFields": {"_score": {"$meta": "textScore"}}})
        sort_stage = {"$sort": {"_score": {"$meta": "textScore"}}}
    else:
        pipeline.append({"$match": match})
        sort_map = {
            "recent": ("created_at", DESCENDING),
            "popular": ("enroll_count", DESCENDING),
            "top_rated": ("ratings_avg", DESCENDING),
            "duration": ("total_duration_minutes", DESCENDING),
        }
        field, direction = sort_map.get(sort_by, ("created_at", DESCENDING))
        sort_stage = {"$sort": {field: direction}}

    pipeline.extend([
        {"$facet": {
            "items": [
                sort_stage,
                {"$skip": (page - 1) * page_size},
                {"$limit": page_size},
                {"$addFields": {"_id": {"$toString": "$_id"}}}
            ],
            "totalCount": [{"$count": "count"}]
        }}
    ])

    doc = list(db.courses.aggregate(pipeline))
    if not doc:
        return 0, []
    total = (doc[0]["totalCount"][0]["count"] if doc[0]["totalCount"] else 0)
    items = doc[0]["items"]
    return total, items
