# services/performance_decorator.py
import time
import functools
from typing import Callable, Awaitable, Any, Optional
from redis.asyncio import Redis
from services.performance_metrics import get_metrics_collector

def monitor_performance(operation_name: str, track_cache_hits: bool = True):
    """
    Decorator to automatically monitor performance of async functions.
    
    Usage:
    @monitor_performance("course_retrieval", track_cache_hits=True)
    async def get_course(db, redis, course_id):
        ...
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract Redis instance from kwargs if available
            redis: Optional[Redis] = kwargs.get('r') or kwargs.get('redis')
            
            start_time = time.perf_counter()
            cache_hit = False
            error = None
            
            try:
                # Check if this is likely a cache hit by monitoring cache stats before/after
                if redis and track_cache_hits:
                    initial_hits = await redis.info('stats')
                    initial_hit_count = initial_hits.get('keyspace_hits', 0)
                
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Check if cache hit occurred
                if redis and track_cache_hits:
                    final_hits = await redis.info('stats')
                    final_hit_count = final_hits.get('keyspace_hits', 0)
                    cache_hit = final_hit_count > initial_hit_count
                
                return result
                
            except Exception as e:
                error = str(e)
                raise
            
            finally:
                # Record performance metrics
                response_time = time.perf_counter() - start_time
                
                if redis:
                    try:
                        collector = get_metrics_collector(redis)
                        await collector.record_request(
                            operation=operation_name,
                            response_time=response_time,
                            cache_hit=cache_hit,
                            error=error
                        )
                    except Exception:
                        # Don't let metrics collection break the main function
                        pass
        
        return wrapper
    return decorator

def monitor_cache_operation(operation_name: str, cache_layer: str = "unknown"):
    """
    Specialized decorator for cache operations that tracks cache-specific metrics.
    
    Usage:
    @monitor_cache_operation("course_cache_get", cache_layer="L1")
    async def get_from_cache(key):
        ...
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            redis: Optional[Redis] = kwargs.get('r') or kwargs.get('redis')
            
            start_time = time.perf_counter()
            error = None
            cache_hit = False
            
            try:
                result = await func(*args, **kwargs)
                # If result is not None, consider it a cache hit
                cache_hit = result is not None
                return result
                
            except Exception as e:
                error = str(e)
                raise
            
            finally:
                response_time = time.perf_counter() - start_time
                
                if redis:
                    try:
                        collector = get_metrics_collector(redis)
                        await collector.record_request(
                            operation=f"{operation_name}_{cache_layer}",
                            response_time=response_time,
                            cache_hit=cache_hit,
                            error=error
                        )
                    except Exception:
                        pass
        
        return wrapper
    return decorator