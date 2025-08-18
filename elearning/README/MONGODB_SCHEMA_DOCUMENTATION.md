# MongoDB Schema Documentation
## E-Learning Platform Database Architecture

**Document Version:** 1.0  
**Date:** December 2024  
**Database:** MongoDB 6.0 with Replica Set (rs0)  
**Platform:** E-Learning Management System  

---

## Executive Summary

This document outlines the MongoDB database schema for our e-learning platform, designed to support scalable online education delivery. The database architecture leverages MongoDB's document-oriented structure to provide flexible content management, real-time progress tracking, and comprehensive analytics capabilities.

### Key Features
- **High Availability**: Replica set configuration ensures 99.9% uptime
- **Scalable Architecture**: Document-based design supports rapid feature expansion
- **Real-time Analytics**: Optimized for live progress tracking and reporting
- **Data Integrity**: Comprehensive indexing and validation strategies

---

## Database Configuration

### Connection Details
```
Database Name: elearning
Replica Set: rs0
Connection URI: mongodb://elearning-mongo:27017/elearning?replicaSet=rs0
```

### Infrastructure
- **Primary Database**: MongoDB 6.0 (Docker containerized)
- **Caching Layer**: Redis 7.0 for performance optimization
- **Backup Strategy**: Replica set with automated failover
- **Security**: Network isolation with Docker networking

---

## Schema Overview

The database consists of three primary collections optimized for educational content delivery:

| Collection | Purpose | Document Count (Est.) | Size (Est.) |
|------------|---------|----------------------|-------------|
| `users` | User authentication and profiles | 10,000+ | 50MB |
| `courses` | Course content and metadata | 1,000+ | 500MB |
| `progress` | Student learning analytics | 100,000+ | 200MB |

---

## Collection Schemas

### 1. Users Collection

**Purpose**: Manages user authentication, profiles, and role-based access control.

#### Document Structure
```json
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "hashed_password": "$2b$12$...",
  "full_name": "John Doe",
  "role": "student|instructor|admin",
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "last_login": ISODate("2024-01-01T00:00:00Z"),
  "profile": {
    "avatar_url": "https://...",
    "bio": "User biography",
    "preferences": {
      "language": "en",
      "notifications": true
    }
  }
}
```

#### Indexes
```javascript
// Unique email index for authentication
db.users.createIndex({ "email": 1 }, { unique: true })

// Role-based queries
db.users.createIndex({ "role": 1, "created_at": -1 })
```

#### Business Rules
- **Email Uniqueness**: Enforced at database level
- **Password Security**: BCrypt hashing with salt rounds
- **Role Hierarchy**: student < instructor < admin

---

### 2. Courses Collection

**Purpose**: Stores comprehensive course content, metadata, and hierarchical lesson structure.

#### Document Structure
```json
{
  "_id": ObjectId("..."),
  "title": "Advanced Python Programming",
  "description": "Comprehensive Python course...",
  "slug": "advanced-python-programming",
  "category": "Programming",
  "tags": ["python", "programming", "advanced"],
  "difficulty": "advanced",
  "language": "en",
  "instructor_id": "user_object_id_string",
  
  "modules": [
    {
      "module_id": "uuid-string",
      "title": "Introduction to Advanced Concepts",
      "index": 0,
      "lessons": [
        {
          "lesson_id": "uuid-string",
          "title": "Decorators and Metaclasses",
          "content_type": "video|article|quiz",
          "duration_minutes": 45,
          "quiz": {
            "question_count": 10,
            "passing_score": 80,
            "max_score": 100
          }
        }
      ]
    }
  ],
  
  // Denormalized fields for performance
  "total_duration_minutes": 1200,
  "lessons_count": 25,
  "ratings_avg": 4.7,
  "ratings_count": 156,
  "enroll_count": 1250,
  
  "published": true,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

#### Indexes
```javascript
// Full-text search across title, description, and tags
db.courses.createIndex(
  { "title": "text", "description": "text", "tags": "text" },
  { name: "courses_text" }
)

// Category and filtering
db.courses.createIndex({
  "category": 1,
  "published": 1,
  "difficulty": 1
})

// Instructor courses
db.courses.createIndex({
  "instructor_id": 1,
  "created_at": -1
})

// Unique slug for SEO
db.courses.createIndex({ "slug": 1 }, { unique: true, sparse: true })
```

#### Design Decisions
- **Embedded Documents**: Modules and lessons stored as nested arrays for atomic updates
- **Denormalization**: Pre-calculated metrics (duration, lesson count) for fast queries
- **UUID Identifiers**: Lessons and modules use UUIDs for client-side generation
- **Text Search**: MongoDB text indexes enable full-text course discovery

---

### 3. Progress Collection

**Purpose**: Tracks detailed student learning progress, completion status, and engagement metrics.

#### Document Structure
```json
{
  "_id": ObjectId("..."),
  "user_id": "user_object_id_string",
  "course_id": "course_object_id_string",
  
  "progress_percent": 75.5,
  "total_lessons": 25,
  
  "completed_lessons": [
    {
      "lesson_id": "uuid-string",
      "completed_at": ISODate("2024-01-01T10:30:00Z")
    }
  ],
  
  "video_watch_times": {
    "lesson-uuid-1": 1800,  // seconds watched
    "lesson-uuid-2": 2700
  },
  
  "quiz_attempts": [
    {
      "lesson_id": "uuid-string",
      "score": 85,
      "max_score": 100,
      "attempted_at": ISODate("2024-01-01T11:00:00Z"),
      "answers": [
        {
          "question_id": "q1",
          "selected": "option_b",
          "correct": true
        }
      ]
    }
  ],
  
  "last_accessed": ISODate("2024-01-01T12:00:00Z"),
  "created_at": ISODate("2024-01-01T09:00:00Z"),
  "updated_at": ISODate("2024-01-01T12:00:00Z")
}
```

#### Indexes
```javascript
// Unique constraint: one progress record per user-course pair
db.progress.createIndex(
  { "user_id": 1, "course_id": 1 },
  { unique: true, name: "user_course_unique" }
)

// User dashboard queries
db.progress.createIndex({
  "user_id": 1,
  "last_accessed": -1
}, { name: "user_last_accessed" })

// Course analytics
db.progress.createIndex({ "course_id": 1 }, { name: "by_course" })

// Video engagement analytics
db.progress.createIndex({ "video_watch_times": 1 })
```

#### Analytics Capabilities
- **Completion Tracking**: Granular lesson-level progress monitoring
- **Engagement Metrics**: Video watch time analysis for content optimization
- **Learning Patterns**: Quiz performance and attempt history
- **Real-time Updates**: Live progress updates using MongoDB change streams

---

## Performance Optimizations

### Indexing Strategy
- **Compound Indexes**: Multi-field indexes for complex queries
- **Text Indexes**: Full-text search capabilities across course content
- **Sparse Indexes**: Optional fields (slug) indexed only when present
- **TTL Indexes**: Automatic cleanup of temporary data (sessions, cache)

### Query Optimization
- **Aggregation Pipelines**: Complex analytics queries using MongoDB aggregation
- **Projection**: Selective field retrieval to minimize network overhead
- **Pagination**: Efficient cursor-based pagination for large result sets
- **Caching**: Redis integration for frequently accessed data

### Data Modeling Best Practices
- **Denormalization**: Strategic duplication of frequently accessed data
- **Embedded vs Referenced**: Lessons embedded in courses for atomic updates
- **Schema Validation**: JSON schema validation for data integrity
- **Atomic Operations**: Single-document transactions where possible

---

## Security & Compliance

### Data Protection
- **Encryption**: Data encrypted at rest and in transit
- **Authentication**: JWT-based authentication with refresh tokens
- **Authorization**: Role-based access control (RBAC)
- **Input Validation**: Pydantic schemas for API data validation

### Privacy Considerations
- **PII Handling**: Personal information stored with appropriate access controls
- **Data Retention**: Configurable retention policies for user data
- **Audit Logging**: Comprehensive logging of data access and modifications
- **GDPR Compliance**: User data export and deletion capabilities

---

## Monitoring & Maintenance

### Performance Metrics
- **Query Performance**: Index usage and slow query monitoring
- **Connection Pooling**: Optimized connection management
- **Replica Set Health**: Primary/secondary node monitoring
- **Storage Growth**: Capacity planning and optimization

### Backup Strategy
- **Replica Set**: Automatic failover and data redundancy
- **Point-in-Time Recovery**: Continuous backup with restore capabilities
- **Cross-Region Replication**: Geographic distribution for disaster recovery
- **Automated Testing**: Regular backup restoration testing

---

## Scalability Roadmap

### Horizontal Scaling
- **Sharding Strategy**: Planned sharding keys for future growth
- **Read Replicas**: Additional secondary nodes for read scaling
- **Geographic Distribution**: Multi-region deployment capabilities
- **Microservices**: Service-oriented architecture for independent scaling

### Capacity Planning
- **Current Capacity**: 1M+ documents across all collections
- **Growth Projections**: 300% annual growth anticipated
- **Resource Allocation**: CPU, memory, and storage scaling plans
- **Cost Optimization**: Efficient resource utilization strategies

---

## Technical Specifications

### MongoDB Configuration
```yaml
# Replica Set Configuration
replication:
  replSetName: "rs0"
  
# Storage Engine
storage:
  engine: wiredTiger
  wiredTiger:
    engineConfig:
      cacheSizeGB: 2
      
# Security
security:
  authorization: enabled
  
# Profiling
operationProfiling:
  slowOpThresholdMs: 100
```

### Connection Pooling
```python
# PyMongo Configuration
client = MongoClient(
    "mongodb://elearning-mongo:27017/elearning?replicaSet=rs0",
    maxPoolSize=50,
    minPoolSize=10,
    maxIdleTimeMS=30000,
    serverSelectionTimeoutMS=5000
)
```

---

## Conclusion

This MongoDB schema provides a robust foundation for our e-learning platform, designed to scale with business growth while maintaining high performance and data integrity. The document-oriented approach enables rapid feature development and supports complex educational workflows.

### Key Benefits
- **Flexibility**: Schema evolution without downtime
- **Performance**: Optimized for read-heavy educational workloads
- **Reliability**: High availability through replica set configuration
- **Analytics**: Rich data structure supports comprehensive reporting
