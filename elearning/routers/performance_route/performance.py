# routers/performance_route/performance.py
import time
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any, List, Optional
from redis.asyncio import Redis
from pymongo.database import Database

from deps import get_redis, get_db
from auth.dependencies import require_role
from services.performance_analysis import PerformanceBenchmark
from repos import courses as course_repo
from fastapi.concurrency import run_in_threadpool

router = APIRouter(
    prefix="/performance", 
    tags=["performance"]
)

@router.post("/benchmark/course-retrieval")
async def benchmark_course_retrieval(
    course_id: str,
    iterations: int = Query(100, ge=10, le=1000),
    concurrent_requests: int = Query(10, ge=1, le=50),
    db: Database = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Benchmark course retrieval performance comparing cached vs non-cached operations.
    
    - **course_id**: ID of the course to benchmark
    - **iterations**: Number of requests to make (10-1000)
    - **concurrent_requests**: Number of concurrent requests (1-50)
    """
    
    # Verify course exists
    course = await run_in_threadpool(course_repo.get_course_by_id, db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    benchmark = PerformanceBenchmark(db, redis)
    result = await benchmark.benchmark_course_retrieval(
        course_id, iterations, concurrent_requests
    )
    
    return {
        "benchmark_type": "course_retrieval",
        "course_id": course_id,
        "test_parameters": {
            "iterations": iterations,
            "concurrent_requests": concurrent_requests
        },
        "results": {
            "cached": {
                "avg_response_time_ms": round(result.cached_metrics.avg_response_time * 1000, 2),
                "min_response_time_ms": round(result.cached_metrics.min_response_time * 1000, 2),
                "max_response_time_ms": round(result.cached_metrics.max_response_time * 1000, 2),
                "p95_response_time_ms": round(result.cached_metrics.p95_response_time * 1000, 2),
                "throughput_ops_per_sec": round(result.cached_metrics.throughput, 2),
                "cache_hit_ratio": result.cached_metrics.cache_hit_ratio
            },
            "non_cached": {
                "avg_response_time_ms": round(result.non_cached_metrics.avg_response_time * 1000, 2),
                "min_response_time_ms": round(result.non_cached_metrics.min_response_time * 1000, 2),
                "max_response_time_ms": round(result.non_cached_metrics.max_response_time * 1000, 2),
                "p95_response_time_ms": round(result.non_cached_metrics.p95_response_time * 1000, 2),
                "throughput_ops_per_sec": round(result.non_cached_metrics.throughput, 2)
            },
            "performance_improvement_percent": round(result.performance_improvement, 2),
            "throughput_improvement_percent": round(result.throughput_improvement, 2)
        }
    }

@router.post("/benchmark/course-listing")
async def benchmark_course_listing(
    iterations: int = Query(50, ge=5, le=500),
    concurrent_requests: int = Query(5, ge=1, le=20),
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    db: Database = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Benchmark course listing performance comparing cached vs non-cached operations.
    
    - **iterations**: Number of requests to make (5-500)
    - **concurrent_requests**: Number of concurrent requests (1-20)
    - **category**: Optional category filter
    - **difficulty**: Optional difficulty filter
    """
    
    filters = {}
    if category:
        filters["category"] = category
    if difficulty:
        filters["difficulty"] = difficulty
    
    benchmark = PerformanceBenchmark(db, redis)
    result = await benchmark.benchmark_course_listing(
        filters, iterations, concurrent_requests
    )
    
    return {
        "benchmark_type": "course_listing",
        "test_parameters": {
            "iterations": iterations,
            "concurrent_requests": concurrent_requests,
            "filters": filters
        },
        "results": {
            "cached": {
                "avg_response_time_ms": round(result.cached_metrics.avg_response_time * 1000, 2),
                "min_response_time_ms": round(result.cached_metrics.min_response_time * 1000, 2),
                "max_response_time_ms": round(result.cached_metrics.max_response_time * 1000, 2),
                "p95_response_time_ms": round(result.cached_metrics.p95_response_time * 1000, 2),
                "throughput_ops_per_sec": round(result.cached_metrics.throughput, 2)
            },
            "non_cached": {
                "avg_response_time_ms": round(result.non_cached_metrics.avg_response_time * 1000, 2),
                "min_response_time_ms": round(result.non_cached_metrics.min_response_time * 1000, 2),
                "max_response_time_ms": round(result.non_cached_metrics.max_response_time * 1000, 2),
                "p95_response_time_ms": round(result.non_cached_metrics.p95_response_time * 1000, 2),
                "throughput_ops_per_sec": round(result.non_cached_metrics.throughput, 2)
            },
            "performance_improvement_percent": round(result.performance_improvement, 2),
            "throughput_improvement_percent": round(result.throughput_improvement, 2)
        }
    }

@router.post("/benchmark/mixed-workload")
async def benchmark_mixed_workload(
    course_count: int = Query(5, ge=3, le=10),
    db: Database = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Benchmark mixed workload with different cache scenarios.
    
    - **course_count**: Number of courses to test (3-10)
    """
    
    # Get sample course IDs
    total, courses = await run_in_threadpool(
        course_repo.list_courses, db, 
        q=None, filters={}, page=1, page_size=course_count, sort_by="recent"
    )
    
    if len(courses) < course_count:
        raise HTTPException(
            status_code=400, 
            detail=f"Not enough courses available. Found {len(courses)}, need {course_count}"
        )
    
    course_ids = [course["_id"] for course in courses]
    
    benchmark = PerformanceBenchmark(db, redis)
    result = await benchmark.benchmark_mixed_workload(course_ids)
    
    return {
        "benchmark_type": "mixed_workload",
        "test_parameters": {
            "course_count": course_count,
            "course_ids": course_ids
        },
        "results": {
            "cold_cache_avg_ms": round(result["cold_cache_avg"] * 1000, 2),
            "warm_cache_avg_ms": round(result["warm_cache_avg"] * 1000, 2),
            "mixed_cache_avg_ms": round(result["mixed_cache_avg"] * 1000, 2),
            "cache_effectiveness_percent": round(result["cache_effectiveness"], 2)
        }
    }

@router.get("/system-summary")
async def get_system_performance_summary(
    db: Database = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get overall system performance metrics and recommendations.
    """
    
    benchmark = PerformanceBenchmark(db, redis)
    summary = await benchmark.get_system_performance_summary()
    
    return {
        "system_performance": summary,
        "timestamp": time.time()
    }

@router.post("/stress-test")
async def run_stress_test(
    duration_seconds: int = Query(30, ge=10, le=300),
    concurrent_users: int = Query(20, ge=5, le=100),
    db: Database = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Run a stress test to evaluate system performance under load.
    
    - **duration_seconds**: Test duration (10-300 seconds)
    - **concurrent_users**: Number of concurrent users (5-100)
    """
    
    import asyncio
    import time
    import random
    
    # Get sample courses for testing
    total, courses = await run_in_threadpool(
        course_repo.list_courses, db, 
        q=None, filters={}, page=1, page_size=20, sort_by="recent"
    )
    
    if not courses:
        raise HTTPException(status_code=400, detail="No courses available for testing")
    
    course_ids = [course["_id"] for course in courses]
    
    results = {
        "successful_requests": 0,
        "failed_requests": 0,
        "response_times": [],
        "errors": []
    }
    
    async def simulate_user():
        """Simulate a single user's behavior"""
        from services.course_service import get_course, list_courses
        
        while True:
            try:
                start_time = time.perf_counter()
                
                # Random operation: 70% course retrieval, 30% course listing
                if random.random() < 0.7:
                    course_id = random.choice(course_ids)
                    await get_course(db, redis, course_id)
                else:
                    await list_courses(
                        db, redis, 
                        q=None, filters={}, page=1, page_size=12, sort_by="recent"
                    )
                
                response_time = time.perf_counter() - start_time
                results["response_times"].append(response_time)
                results["successful_requests"] += 1
                
                # Small delay between requests
                await asyncio.sleep(random.uniform(0.1, 0.5))
                
            except Exception as e:
                results["failed_requests"] += 1
                results["errors"].append(str(e))
    
    # Start concurrent users
    tasks = [asyncio.create_task(simulate_user()) for _ in range(concurrent_users)]
    
    # Run for specified duration
    await asyncio.sleep(duration_seconds)
    
    # Cancel all tasks
    for task in tasks:
        task.cancel()
    
    # Wait for tasks to complete cancellation
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Calculate statistics
    if results["response_times"]:
        import statistics
        avg_response_time = statistics.mean(results["response_times"])
        p95_response_time = statistics.quantiles(results["response_times"], n=20)[18]
        total_requests = results["successful_requests"] + results["failed_requests"]
        throughput = total_requests / duration_seconds
    else:
        avg_response_time = 0
        p95_response_time = 0
        total_requests = 0
        throughput = 0
    
    return {
        "stress_test_results": {
            "test_parameters": {
                "duration_seconds": duration_seconds,
                "concurrent_users": concurrent_users
            },
            "performance_metrics": {
                "total_requests": total_requests,
                "successful_requests": results["successful_requests"],
                "failed_requests": results["failed_requests"],
                "success_rate_percent": (results["successful_requests"] / max(1, total_requests)) * 100,
                "avg_response_time_ms": round(avg_response_time * 1000, 2),
                "p95_response_time_ms": round(p95_response_time * 1000, 2),
                "throughput_requests_per_sec": round(throughput, 2)
            },
            "errors": results["errors"][:10]  # Show first 10 errors
        }
    }

@router.get("/compare/cache-layers")
async def compare_cache_layers(
    operation: str = Query("course_retrieval"),
    sample_size: int = Query(100, ge=10, le=500),
    db: Database = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Compare performance between different cache layers (L1 memory vs L2 Redis vs Database).
    
    - **operation**: Operation to test
    - **sample_size**: Number of samples per test
    """
    import time
    import statistics
    from services.memory_cache import memory_cache
    from repos import courses as course_repo
    
    # Get a sample course for testing
    total, courses = await run_in_threadpool(
        course_repo.list_courses, db, 
        q=None, filters={}, page=1, page_size=1, sort_by="recent"
    )
    
    if not courses:
        raise HTTPException(status_code=400, detail="No courses available for testing")
    
    course_id = courses[0]["_id"]
    
    # Test L1 Cache (Memory)
    from services.cache_keys import course_key
    key = course_key(course_id)
    
    # Pre-populate L1 cache
    course_data = await run_in_threadpool(course_repo.get_course_by_id, db, course_id)
    await memory_cache.set(key, course_data, ttl=300)
    
    l1_times = []
    for _ in range(sample_size):
        start = time.perf_counter()
        await memory_cache.get(key)
        l1_times.append(time.perf_counter() - start)
    
    # Test L2 Cache (Redis)
    import json
    from repos.helper import JSONEncoder
    await redis.set(key, json.dumps(course_data, cls=JSONEncoder), ex=300)
    
    l2_times = []
    for _ in range(sample_size):
        start = time.perf_counter()
        await redis.get(key)
        l2_times.append(time.perf_counter() - start)
    
    # Test Database
    db_times = []
    for _ in range(min(sample_size, 50)):  # Limit DB calls
        start = time.perf_counter()
        await run_in_threadpool(course_repo.get_course_by_id, db, course_id)
        db_times.append(time.perf_counter() - start)
    
    return {
        "cache_layer_comparison": {
            "l1_memory_cache": {
                "avg_response_time_ms": round(statistics.mean(l1_times) * 1000, 4),
                "min_response_time_ms": round(min(l1_times) * 1000, 4),
                "max_response_time_ms": round(max(l1_times) * 1000, 4),
                "sample_size": len(l1_times)
            },
            "l2_redis_cache": {
                "avg_response_time_ms": round(statistics.mean(l2_times) * 1000, 4),
                "min_response_time_ms": round(min(l2_times) * 1000, 4),
                "max_response_time_ms": round(max(l2_times) * 1000, 4),
                "sample_size": len(l2_times)
            },
            "database": {
                "avg_response_time_ms": round(statistics.mean(db_times) * 1000, 2),
                "min_response_time_ms": round(min(db_times) * 1000, 2),
                "max_response_time_ms": round(max(db_times) * 1000, 2),
                "sample_size": len(db_times)
            },
            "performance_ratios": {
                "l2_vs_l1_ratio": round(statistics.mean(l2_times) / statistics.mean(l1_times), 2),
                "db_vs_l1_ratio": round(statistics.mean(db_times) / statistics.mean(l1_times), 2),
                "db_vs_l2_ratio": round(statistics.mean(db_times) / statistics.mean(l2_times), 2)
            }
        },
        "test_parameters": {
            "course_id": course_id,
            "sample_size": sample_size
        }
    }

@router.get("/health")
async def performance_health(
    redis: Redis = Depends(get_redis)
):
    """
    Get basic performance health status (no authentication required).
    """
    from services.cache_service import get_cache_stats
    
    try:
        cache_stats = await get_cache_stats(redis)
        total_hits = cache_stats.get("redis_hits", 0)
        total_misses = cache_stats.get("redis_misses", 0)
        total_requests = total_hits + total_misses
        hit_ratio = (total_hits / max(1, total_requests)) * 100
        
        return {
            "status": "healthy",
            "cache_performance": {
                "hit_ratio_percent": round(hit_ratio, 1),
                "total_requests": total_requests,
                "redis_keys": cache_stats.get("redis_keys", 0),
                "memory_cache_size": cache_stats.get("memory_cache_size", 0)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }