"""Rate limiting middleware."""
import time
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.utils.logger import logger

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using in-memory store."""
    
    def __init__(self, app, requests_per_minute: int = 10, requests_per_day: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self.minute_requests: Dict[str, list] = {}  # IP -> list of timestamps (minute)
        self.day_requests: Dict[str, list] = {}     # IP -> list of timestamps (day)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks, static endpoints, or in debug mode
        skip_paths = ["/api/v1/health", "/", "/docs", "/redoc", "/openapi.json"]
        if request.url.path in skip_paths or settings.debug:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limits
        if not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        
        return await call_next(request)
    
    def _check_rate_limit(self, ip: str) -> bool:
        """Check if request is within rate limits."""
        now = time.time()
        minute_window = 60  # 1 minute
        day_window = 86400  # 24 hours
        
        # Check minute limit
        minute_requests = self.minute_requests.get(ip, [])
        minute_requests = [t for t in minute_requests if now - t < minute_window]
        
        if len(minute_requests) >= self.requests_per_minute:
            return False
        
        # Check day limit
        day_requests = self.day_requests.get(ip, [])
        day_requests = [t for t in day_requests if now - t < day_window]
        
        if len(day_requests) >= self.requests_per_day:
            return False
        
        # Add current request
        minute_requests.append(now)
        day_requests.append(now)
        self.minute_requests[ip] = minute_requests
        self.day_requests[ip] = day_requests
        
        return True
    
    def get_limit_info(self, ip: str) -> Dict[str, any]:
        """Get remaining requests and reset time."""
        now = time.time()
        minute_window = 60
        day_window = 86400
        
        minute_requests = self.minute_requests.get(ip, [])
        minute_requests = [t for t in minute_requests if now - t < minute_window]
        
        day_requests = self.day_requests.get(ip, [])
        day_requests = [t for t in day_requests if now - t < day_window]
        
        minute_remaining = max(0, self.requests_per_minute - len(minute_requests))
        day_remaining = max(0, self.requests_per_day - len(day_requests))
        
        minute_reset = min(minute_requests) + minute_window if minute_requests else now + minute_window
        day_reset = min(day_requests) + day_window if day_requests else now + day_window
        
        return {
            "minute": {
                "remaining": minute_remaining,
                "limit": self.requests_per_minute,
                "reset_at": int(minute_reset)
            },
            "day": {
                "remaining": day_remaining,
                "limit": self.requests_per_day,
                "reset_at": int(day_reset)
            }
        }
