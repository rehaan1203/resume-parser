"""Request/response monitoring middleware."""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import logger

try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available. Metrics disabled.")

if PROMETHEUS_AVAILABLE:
    # Prometheus metrics
    REQUESTS = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
    REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
    REQUESTS_IN_PROGRESS = Gauge('http_requests_in_progress', 'HTTP requests in progress')
    ACTIVE_USERS = Gauge('active_users', 'Active users')
    CACHE_HITS = Counter('cache_hits_total', 'Total cache hits')
    CACHE_MISSES = Counter('cache_misses_total', 'Total cache misses')

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Monitor request/response metrics."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with monitoring."""
        method = request.method
        endpoint = request.url.path
        
        # Track in-progress requests
        if PROMETHEUS_AVAILABLE:
            REQUESTS_IN_PROGRESS.inc()
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            
            if PROMETHEUS_AVAILABLE:
                REQUESTS.labels(method=method, endpoint=endpoint, status=response.status_code).inc()
                REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
            
            # Log slow requests
            if duration > 2.0:
                logger.warning(f"Slow request: {method} {endpoint} took {duration:.2f}s")
            
            return response
            
        except Exception as e:
            # Record error
            if PROMETHEUS_AVAILABLE:
                REQUESTS.labels(method=method, endpoint=endpoint, status=500).inc()
            raise
            
        finally:
            if PROMETHEUS_AVAILABLE:
                REQUESTS_IN_PROGRESS.dec()
    
    @staticmethod
    def record_cache_hit():
        """Record cache hit."""
        if PROMETHEUS_AVAILABLE:
            CACHE_HITS.inc()
    
    @staticmethod
    def record_cache_miss():
        """Record cache miss."""
        if PROMETHEUS_AVAILABLE:
            CACHE_MISSES.inc()
    
    @staticmethod
    def update_active_users(count: int):
        """Update active users count."""
        if PROMETHEUS_AVAILABLE:
            ACTIVE_USERS.set(count)
