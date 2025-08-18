# services/performance_metrics.py
from typing import Optional
from redis.asyncio import Redis

class PerformanceMetricsCollector:
    def __init__(self, redis: Redis):
        self.redis = redis

metrics_collector: Optional[PerformanceMetricsCollector] = None

def get_metrics_collector(redis: Redis) -> PerformanceMetricsCollector:
    global metrics_collector
    if metrics_collector is None:
        metrics_collector = PerformanceMetricsCollector(redis)
    return metrics_collector