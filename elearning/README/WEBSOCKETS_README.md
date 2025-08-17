# WebSocket Real-Time Analytics

## Overview
Real-time analytics system using WebSockets to broadcast live updates for course analytics and platform overview data.

## Architecture

### Components Used
- **FastAPI WebSockets** - Real-time bidirectional communication
- **Redis Pub/Sub** - Message broadcasting between services
- **MongoDB** - Analytics data storage
- **Two-level caching** - Memory + Redis for performance

### Why WebSockets?
- **Real-time updates** - Instant analytics without polling
- **Low latency** - Direct connection for live data
- **Efficient** - Single connection for multiple updates
- **Scalable** - Redis pub/sub handles multiple instances

## WebSocket Endpoints

### 1. Course Analytics
```
ws://localhost:8000/realtime/course/{course_id}
```
**Purpose**: Real-time course-specific analytics
**Receives**: Course performance updates, student progress, video watch times

**Message Format**:
```json
{
  "event": "course_analytics_update",
  "course_id": "68a1e085f965e83b626e215e",
  "analytics": {
    "course_id": "68a1e085f965e83b626e215e",
    "students": 1,
    "avg_completion": 25.0,
    "total_watch_time_minutes": 0.0,
    "avg_watch_time_per_student": 0.0,
    "avg_quiz_score": 0,
    "generated_at": "2025-08-17T14:19:59.666684"
  }
}
```

### 2. Instructor Dashboard
```
ws://localhost:8000/realtime/instructor/{instructor_id}
```
**Purpose**: Platform-wide analytics for instructors
**Receives**: Platform overview updates, global statistics

**Message Format**:
```json
{
  "event": "platform_overview",
  "data": {
    "total_courses": 14,
    "active_students": 3,
    "avg_rating": 0.0,
    "popular_categories": [
      {"_id": "Data", "count": 12},
      {"_id": "Backend", "count": 1}
    ],
    "generated_at": "2025-08-17T14:00:37.754884"
  }
}
```

## Trigger Events

### Progress Events
- **Lesson Completion**: `/progress/lessons/{lesson_id}/complete`
- **Video Watch Time**: `/progress/lessons/{lesson_id}/watch-time`

### Course Events  
- **Course Creation**: `/courses` (POST)
- **Course Updates**: `/courses/{course_id}` (PUT)
- **Module Updates**: `/courses/{course_id}/modules/{module_id}` (PUT)

## Implementation Flow

1. **Event Trigger** → API endpoint called
2. **Cache Invalidation** → Related analytics caches cleared
3. **Redis Pub/Sub** → Event published to `analytics:{course_id}` or `analytics:platform`
4. **WebSocket Broadcast** → Fresh analytics sent to connected clients
5. **Cache Refresh** → New data cached for next requests

## Connection Management

### Course Connections
- Multiple WebSockets per course
- Automatic cleanup of dead connections
- Course-specific message routing

### Instructor Connections  
- One WebSocket per instructor
- Platform-wide updates only
- Global analytics broadcasting

## Usage Example

```javascript
// Connect to course analytics
const courseWs = new WebSocket('ws://localhost:8000/realtime/course/68a1e085f965e83b626e215e');
courseWs.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateCourseAnalytics(data.analytics);
};

// Connect to instructor dashboard
const instructorWs = new WebSocket('ws://localhost:8000/realtime/instructor/689f3b634ccdaf5428b24d62');
instructorWs.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updatePlatformOverview(data.data);
};
```

## Benefits

- **Instant Updates** - No page refresh needed
- **Reduced Server Load** - No constant polling
- **Better UX** - Live data visualization
- **Scalable** - Redis handles distribution
- **Efficient** - Cached analytics with smart invalidation