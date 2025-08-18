# services/performance_analysis.py

# Standard library imports for timing, async operations and statistics
import time
import asyncio
import statistics
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass

# Third party imports for Redis, MongoDB and FastAPI
from redis.asyncio import Redis
from pymongo.database import Database
from fastapi.concurrency import run_in_threadpool

# Local imports for course and cache related functionality
from repos import courses as course_repo
from services.course_service import get_course, list_courses
from services.cache_service import get_cache_stats
from services.memory_cache import memory_cache

# Data class to store performance metrics for an operation
@dataclass
class PerformanceMetrics:
    operation: str  # Name of the operation being measured
    cached: bool    # Whether the operation used caching
    response_times: List[float]  # List of individual response times
    avg_response_time: float     # Average response time
    min_response_time: float     # Minimum response time
    max_response_time: float     # Maximum response time
    throughput: float  # Operations per second
    cache_hit_ratio: Optional[float] = None  # Cache hit ratio if applicable
    memory_usage: Optional[str] = None       # Memory usage if available

# Data class to compare cached vs non-cached performance
@dataclass
class ComparisonResult:
    operation: str                       # Name of operation being compared
    cached_metrics: PerformanceMetrics   # Metrics with caching enabled
    non_cached_metrics: PerformanceMetrics  # Metrics without caching
    performance_improvement: float  # Percentage improvement in response time
    throughput_improvement: float  # Percentage improvement in throughput

class PerformanceBenchmark:
    """Class for benchmarking performance of course operations with and without caching"""
    
    def __init__(self, db: Database, redis: Redis):
        self.db = db
        self.redis = redis
        
    async def measure_operation(
        self, 
        operation_func: Callable[..., Awaitable[Any]], 
        iterations: int = 100,
        concurrent_requests: int = 10,
        **kwargs
    ) -> PerformanceMetrics:
        """
        Measure performance metrics for an async operation with concurrent requests
        
        Args:
            operation_func: Async function to benchmark
            iterations: Total number of operations to perform
            concurrent_requests: Number of concurrent requests per batch
            kwargs: Arguments to pass to operation_func
        """
        
        async def single_operation():
            start_time = time.perf_counter()
            await operation_func(**kwargs)
            return time.perf_counter() - start_time
        
        # Run concurrent batches
        response_times = []
        batch_size = concurrent_requests
        batches = iterations // batch_size
        
        overall_start = time.perf_counter()
        
        # Execute batches of concurrent requests
        for _ in range(batches):
            tasks = [single_operation() for _ in range(batch_size)]
            batch_times = await asyncio.gather(*tasks)
            response_times.extend(batch_times)
        
        # Handle any remaining iterations not in full batches
        remaining = iterations % batch_size
        if remaining:
            tasks = [single_operation() for _ in range(remaining)]
            batch_times = await asyncio.gather(*tasks)
            response_times.extend(batch_times)
        
        overall_time = time.perf_counter() - overall_start
        
        return PerformanceMetrics(
            operation=operation_func.__name__,
            cached=True,  # Will be updated by caller
            response_times=response_times,
            avg_response_time=statistics.mean(response_times),
            min_response_time=min(response_times),
            max_response_time=max(response_times),
            throughput=len(response_times) / overall_time
        )

    async def benchmark_course_retrieval(
        self, 
        course_id: str, 
        iterations: int = 100,
        concurrent_requests: int = 10
    ) -> ComparisonResult:
        """
        Compare performance of course retrieval with and without caching
        
        Tests both cached and non-cached scenarios with the same workload
        """
        
        # Clear cache for non-cached test
        await self._clear_course_cache(course_id)
        
        # Define non-cached operation using direct DB access
        async def non_cached_get_course():
            return await run_in_threadpool(course_repo.get_course_by_id, self.db, course_id)
        
        # Measure non-cached performance
        non_cached_metrics = await self.measure_operation(
            non_cached_get_course, iterations, concurrent_requests
        )
        non_cached_metrics.cached = False
        
        # Warm up cache before cached test
        await get_course(self.db, self.redis, course_id)
        
        # Define cached operation using cache service
        async def cached_get_course():
            return await get_course(self.db, self.redis, course_id)
        
        # Measure cached performance
        cached_metrics = await self.measure_operation(
            cached_get_course, iterations, concurrent_requests
        )
        cached_metrics.cached = True
        
        # Get cache stats and update metrics
        cache_stats = await get_cache_stats(self.redis)
        cached_metrics.cache_hit_ratio = cache_stats.get("redis_hits", 0) / max(1, 
            cache_stats.get("redis_hits", 0) + cache_stats.get("redis_misses", 0)) * 100
        cached_metrics.memory_usage = cache_stats.get("redis_memory_used")
        
        return ComparisonResult(
            operation="course_retrieval",
            cached_metrics=cached_metrics,
            non_cached_metrics=non_cached_metrics,
            performance_improvement=self._calculate_improvement(
                non_cached_metrics.avg_response_time, 
                cached_metrics.avg_response_time
            ),
            throughput_improvement=self._calculate_improvement(
                cached_metrics.throughput, 
                non_cached_metrics.throughput, 
                higher_is_better=True
            )
        )

    async def benchmark_course_listing(
        self, 
        filters: Dict[str, Any] = None,
        iterations: int = 50,
        concurrent_requests: int = 5
    ) -> ComparisonResult:
        """
        Compare performance of course listing with and without caching
        
        Args:
            filters: Optional filters to apply to course listing
            iterations: Number of operations to perform
            concurrent_requests: Number of concurrent requests per batch
        """
        
        filters = filters or {}
        
        # Clear cache for non-cached test
        await self._clear_course_list_cache()
        
        # Define non-cached operation
        async def non_cached_list_courses():
            return await run_in_threadpool(
                course_repo.list_courses, 
                self.db, 
                q=None, 
                filters=filters, 
                page=1, 
                page_size=12, 
                sort_by="recent"
            )
        
        # Measure non-cached performance
        non_cached_metrics = await self.measure_operation(
            non_cached_list_courses, iterations, concurrent_requests
        )
        non_cached_metrics.cached = False
        
        # Warm up cache before cached test
        await list_courses(
            self.db, self.redis, 
            q=None, filters=filters, page=1, page_size=12, sort_by="recent"
        )
        
        # Define cached operation
        async def cached_list_courses():
            return await list_courses(
                self.db, self.redis, 
                q=None, filters=filters, page=1, page_size=12, sort_by="recent"
            )
        
        # Measure cached performance
        cached_metrics = await self.measure_operation(
            cached_list_courses, iterations, concurrent_requests
        )
        cached_metrics.cached = True
        
        return ComparisonResult(
            operation="course_listing",
            cached_metrics=cached_metrics,
            non_cached_metrics=non_cached_metrics,
            performance_improvement=self._calculate_improvement(
                non_cached_metrics.avg_response_time, 
                cached_metrics.avg_response_time
            ),
            throughput_improvement=self._calculate_improvement(
                cached_metrics.throughput, 
                non_cached_metrics.throughput, 
                higher_is_better=True
            )
        )

    async def benchmark_mixed_workload(
        self, 
        course_ids: List[str],
        iterations: int = 100
    ) -> Dict[str, Any]:
        """
        Benchmark performance with mixed cache states (cold, warm, and partially warm)
        
        Tests how the system performs under different cache conditions
        """
        
        results = {
            "cold_cache": [],
            "warm_cache": [],
            "mixed_cache": []
        }
        
        # Test with completely cold cache
        await self._clear_all_caches()
        for course_id in course_ids[:5]:  # Test first 5 courses
            start_time = time.perf_counter()
            await get_course(self.db, self.redis, course_id)
            results["cold_cache"].append(time.perf_counter() - start_time)
        
        # Test with fully warmed cache
        for course_id in course_ids[:5]:
            start_time = time.perf_counter()
            await get_course(self.db, self.redis, course_id)
            results["warm_cache"].append(time.perf_counter() - start_time)
        
        # Test with partially warmed cache
        await self._clear_all_caches()
        # Pre-warm half the courses
        for course_id in course_ids[:3]:
            await get_course(self.db, self.redis, course_id)
        
        # Test all courses with mixed cache state
        for course_id in course_ids[:5]:
            start_time = time.perf_counter()
            await get_course(self.db, self.redis, course_id)
            results["mixed_cache"].append(time.perf_counter() - start_time)
        
        return {
            "cold_cache_avg": statistics.mean(results["cold_cache"]),
            "warm_cache_avg": statistics.mean(results["warm_cache"]),
            "mixed_cache_avg": statistics.mean(results["mixed_cache"]),
            "cache_effectiveness": self._calculate_improvement(
                statistics.mean(results["cold_cache"]),
                statistics.mean(results["warm_cache"])
            )
        }

    async def get_system_performance_summary(self) -> Dict[str, Any]:
        """
        Get overall system performance metrics and cache statistics
        
        Returns cache hit ratios, memory usage, and performance recommendations
        """
        
        cache_stats = await get_cache_stats(self.redis)
        memory_cache_size = len(memory_cache._store)
        
        # Calculate cache efficiency metrics
        total_hits = cache_stats.get("redis_hits", 0)
        total_misses = cache_stats.get("redis_misses", 0)
        total_requests = total_hits + total_misses
        
        return {
            "cache_performance": {
                "hit_ratio": (total_hits / max(1, total_requests)) * 100,
                "total_requests": total_requests,
                "redis_keys": cache_stats.get("redis_keys", 0),
                "memory_cache_size": memory_cache_size,
                "redis_memory_used": cache_stats.get("redis_memory_used", "N/A")
            },
            "recommendations": self._generate_recommendations(cache_stats, memory_cache_size)
        }

    def _calculate_improvement(self, baseline: float, optimized: float, higher_is_better: bool = False) -> float:
        """
        Calculate percentage improvement between baseline and optimized values
        
        Args:
            baseline: Original performance value
            optimized: New performance value
            higher_is_better: Whether higher values indicate better performance
        """
        if baseline == 0:
            return 0
        
        if higher_is_better:
            return ((optimized - baseline) / baseline) * 100
        else:
            return ((baseline - optimized) / baseline) * 100

    def _generate_recommendations(self, cache_stats: Dict, memory_cache_size: int) -> List[str]:
        """
        Generate performance optimization recommendations based on metrics
        
        Analyzes cache hit ratios, memory usage, and key counts to suggest improvements
        """
        recommendations = []
        
        total_hits = cache_stats.get("redis_hits", 0)
        total_misses = cache_stats.get("redis_misses", 0)
        hit_ratio = (total_hits / max(1, total_hits + total_misses)) * 100
        
        if hit_ratio < 70:
            recommendations.append("Consider increasing cache TTL or implementing cache warming")
        
        if memory_cache_size > 1000:
            recommendations.append("Memory cache is large - consider implementing LRU eviction")
        
        if cache_stats.get("redis_keys", 0) > 10000:
            recommendations.append("High Redis key count - consider cache key cleanup strategy")
        
        return recommendations

    async def _clear_course_cache(self, course_id: str):
        """Clear both memory and Redis cache for a specific course"""
        from services.cache_keys import course_key
        key = course_key(course_id)
        await memory_cache.delete(key)
        await self.redis.delete(key)

    async def _clear_course_list_cache(self):
        """Clear all course listing related caches from both memory and Redis"""
        await memory_cache.pattern_delete("courses_list:")
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match="courses_list:*", count=200)
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

    async def _clear_all_caches(self):
        """Clear all caches completely from both memory and Redis"""
        memory_cache._store.clear()
        await self.redis.flushdb()
