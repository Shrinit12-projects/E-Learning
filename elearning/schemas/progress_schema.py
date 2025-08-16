from pydantic import BaseModel, Field, constr
from typing import List, Optional
from datetime import datetime

ID = constr(strip_whitespace=True, min_length=1)

class CompleteLessonIn(BaseModel):
    course_id: ID

class CompletedLesson(BaseModel):
    lesson_id: str
    completed_at: datetime

class CourseProgressOut(BaseModel):
    user_id: str
    course_id: str
    progress_percent: float = 0.0
    completed_count: int = 0
    total_lessons: int = 0
    completed_lessons: List[CompletedLesson] = []
    last_accessed: Optional[datetime] = None

class DashboardCourseItem(BaseModel):
    course_id: str
    course_title: str
    slug: Optional[str] = None
    category: Optional[str] = None
    progress_percent: float = 0.0
    completed_count: int = 0
    total_lessons: int = 0
    last_accessed: Optional[datetime] = None

class ProgressDashboardOut(BaseModel):
    user_id: str
    total_courses: int
    completed_courses: int
    average_progress: float
    items: List[DashboardCourseItem]
