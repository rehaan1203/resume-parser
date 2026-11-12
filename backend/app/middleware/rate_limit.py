"""Rate limiting middleware."""
import time
from typing import Dict, Tuple, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.utils.logger import logger

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis (when available) with bounded in-memory fallback."""
    
    def __init__(self, app, requests_per_minute: int = 10, requests_per_day: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self.minute_requests: Dict[str, list] = {}  # IP -> list of timestamps (minute)
        self.day_requests: Dict[str, list] = {}     # IP -> list of timestamps (day)
        self._sweep_counter: int = 0

    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        """Resolve caller IP safely behind reverse proxies via X-Forwarded-For or X-Real-IP."""
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first_ip = xff.split(",")[0].strip()
            if first_ip:
                return first_ip
        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()
        return request.client.host if request.client else "unknown"
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health/connector status checks, static endpoints, or in debug mode
        api_prefix = getattr(settings, "api_prefix", "/api/v1")
        skip_paths = {
            f"{api_prefix}/health",
            f"{api_prefix}/outlook/status",
            f"{api_prefix}/sharepoint/status",
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        if request.url.path in skip_paths or settings.debug:
            return await call_next(request)
        
        client_ip = self._extract_client_ip(request)
        
        if not await self._check_rate_limit_async(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
            )
        
        return await call_next(request)

    async def _check_rate_limit_async(self, ip: str) -> bool:
        """Check rate limits using distributed Redis fixed-window counters when available, else bounded memory."""
        try:
            from app.utils.redis_client import RedisClient
            r = await RedisClient().get_client()
            if r is not None:
                now_int = int(time.time())
                min_key = f"ratelimit:min:{ip}:{now_int // 60}"
                day_key = f"ratelimit:day:{ip}:{now_int // 86400}"
                min_cnt = await r.incr(min_key)
                if min_cnt == 1:
                    await r.expire(min_key, 65)
                if min_cnt > self.requests_per_minute:
                    return False
                day_cnt = await r.incr(day_key)
                if day_cnt == 1:
                    await r.expire(day_key, 86500)
                if day_cnt > self.requests_per_day:
                    return False
                return True
        except Exception:
            pass
        return self._check_rate_limit(ip)

    def _prune_stale_entries(self, now: float) -> None:
        """Evict expired IP keys periodically so in-memory dicts never grow unboundedly."""
        self.minute_requests = {
            k: [t for t in v if now - t < 60]
            for k, v in self.minute_requests.items()
            if any(now - t < 60 for t in v)
        }
        self.day_requests = {
            k: [t for t in v if now - t < 86400]
            for k, v in self.day_requests.items()
            if any(now - t < 86400 for t in v)
        }
    
    def _check_rate_limit(self, ip: str) -> bool:
        """Check if request is within rate limits (in-memory fallback)."""
        now = time.time()
        self._sweep_counter += 1
        if self._sweep_counter % 100 == 0:
            self._prune_stale_entries(now)

        minute_window = 60  # 1 minute
        day_window = 86400  # 24 hours
        
        # Check minute limit
        minute_requests = self.minute_requests.get(ip, [])
        minute_requests = [t for t in minute_requests if now - t < minute_window]
        
        if len(minute_requests) >= self.requests_per_minute:
            self.minute_requests[ip] = minute_requests
            return False
        
        # Check day limit
        day_requests = self.day_requests.get(ip, [])
        day_requests = [t for t in day_requests if now - t < day_window]
        
        if len(day_requests) >= self.requests_per_day:
            self.day_requests[ip] = day_requests
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
