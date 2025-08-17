# services/cache_keys.py

def course_key(course_id: str) -> str:
    return f"course:{course_id}"

def courses_list_key(filters_hash: str) -> str:
    return f"courses_list:{filters_hash}"

def progress_key(user_id: str, course_id: str) -> str:
    return f"progress:{user_id}:{course_id}"

def user_dashboard_key(user_id: str) -> str:
    return f"user_dashboard:{user_id}"

def analytics_course_key(course_id: str) -> str:
    return f"analytics:course:{course_id}"

def analytics_platform_overview_key() -> str:
    return "analytics:platform:overview"

def analytics_student_patterns_key(user_id: str) -> str:
    return f"analytics:student:{user_id}:patterns"

def search_key(query_hash: str) -> str:
    return f"search:{query_hash}"

def popular_courses_key() -> str:
    return "popular_courses"

def user_reco_key(user_id: str) -> str:
    return f"user_recommendations:{user_id}"

# Auth/session
def user_session_key(user_id: str) -> str:
    return f"user_session:{user_id}"

def blacklisted_jti_key(jti: str) -> str:
    return f"blacklisted_tokens:{jti}"

def refresh_tokens_key(user_id: str) -> str:
    return f"refresh_tokens:{user_id}"
