from pydantic import BaseModel, Field, constr
from typing import List, Optional, Literal
from datetime import datetime

# Keep IDs as str at the API boundary. Convert to ObjectId in the repo.
ID = constr(strip_whitespace=True, min_length=1)

class QuizMeta(BaseModel):
    question_count: int = 0
    passing_score: int = 0  # percentage
    max_score: int = 0

class LessonIn(BaseModel):
    lesson_id: str
    title: constr(min_length=1)
    content_type: Literal["video", "article", "quiz"]
    duration_minutes: int = 0

class ModuleIn(BaseModel):
    module_id: str
    title: constr(min_length=1)
    index: int
    lessons: List[LessonIn] = []

class CourseCreate(BaseModel):
    title: constr(min_length=3)
    description: str = ""
    slug: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    difficulty: Optional[Literal["beginner", "intermediate", "advanced"]] = None
    language: Optional[str] = None
    instructor_id: ID
    modules: List[ModuleIn] = []
    published: bool = False

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[Literal["beginner", "intermediate", "advanced"]] = None
    language: Optional[str] = None
    published: Optional[bool] = None

class ModuleUpdate(BaseModel):
    title: Optional[str] = None
    index: Optional[int] = None
    lessons: Optional[List[LessonIn]] = None

class LessonOut(BaseModel):
    lesson_id: str
    title: str
    content_type: str
    duration_minutes: int
    quiz: Optional[QuizMeta] = None

class ModuleOut(BaseModel):
    module_id: str
    title: str
    index: int
    lessons: List[LessonOut]

class CourseOut(BaseModel):
    id: str = Field(alias="_id")
    title: str
    description: str
    slug: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    difficulty: Optional[str] = None
    language: Optional[str] = None
    instructor_id: str
    modules: List[ModuleOut] = []
    total_duration_minutes: int = 0
    lessons_count: int = 0
    ratings_avg: float = 0.0
    ratings_count: int = 0
    enroll_count: int = 0
    published: bool = False
    created_at: datetime
    updated_at: datetime

class CoursesPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[CourseOut]
