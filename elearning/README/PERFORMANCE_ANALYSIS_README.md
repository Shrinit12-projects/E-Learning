# Performance Analysis System

Compares cached vs non-cached operations in your e-learning platform.

## API Endpoints

### Public Endpoints (No Auth Required)
```http
GET /performance/health                    # Basic cache health
GET /performance/system-summary            # System performance overview
GET /performance/metrics/operation/{name}  # Operation-specific metrics
```

### Admin Endpoints (Requires Admin Token)
```http
POST /performance/benchmark/course-retrieval   # Benchmark course retrieval
POST /performance/benchmark/course-listing     # Benchmark course listing
POST /performance/benchmark/mixed-workload     # Test mixed cache scenarios
POST /performance/stress-test                  # Run stress tests
GET  /performance/compare/cache-layers         # Compare L1/L2/DB performance
DELETE /performance/metrics/reset              # Reset metrics
```

## Usage Examples

### Basic Health Check
```bash
curl "http://localhost:8000/performance/health"
```

### System Summary
```bash
curl "http://localhost:8000/performance/system-summary"
```

### Course Retrieval Benchmark (Admin)
```bash
curl -X POST "http://localhost:8000/performance/benchmark/course-retrieval" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"course_id": "course_123", "iterations": 100}'
```

### Cache Layer Comparison (Admin)
```bash
curl "http://localhost:8000/performance/compare/cache-layers" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

## Expected Results

**Typical Performance Improvements:**
- 90-95% faster response times with caching
- 10-50x throughput improvement
- Sub-millisecond cache hits vs 10-100ms database queries

**Cache Layer Performance:**
- L1 Memory: ~0.02ms
- L2 Redis: ~1-2ms  
- Database: ~20-50ms

## Demo Script

Run the complete demo:
```bash
cd elearning
python scripts/performance_demo.py
```