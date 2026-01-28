"""Middleware for rate limiting, request timeouts, and input validation"""
from typing import Callable
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from collections import defaultdict
from datetime import datetime, timedelta
import re

_rate_limit_storage: dict[str, list[datetime]] = defaultdict(list)
_rate_limit_cleanup_interval = timedelta(minutes=5)
_last_cleanup = datetime.now()


def _cleanup_old_entries():
    """Remove old rate limit entries"""
    global _last_cleanup
    now = datetime.now()
    if now - _last_cleanup > _rate_limit_cleanup_interval:
        cutoff = now - timedelta(minutes=1)
        for ip in list(_rate_limit_storage.keys()):
            _rate_limit_storage[ip] = [
                entry for entry in _rate_limit_storage[ip] if entry > cutoff
            ]
            if not _rate_limit_storage[ip]:
                del _rate_limit_storage[ip]
        _last_cleanup = now


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to prevent API abuse"""
    
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
    
    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc", "/"]:
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        _cleanup_old_entries()
        
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        recent_requests = [
            entry for entry in _rate_limit_storage[client_ip]
            if entry > minute_ago
        ]
        hourly_requests = [
            entry for entry in _rate_limit_storage[client_ip]
            if entry > hour_ago
        ]
        if len(recent_requests) >= self.requests_per_minute:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "message": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_minute} requests per minute allowed. Please try again later."
                }
            )
        
        if len(hourly_requests) >= self.requests_per_hour:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "message": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_hour} requests per hour allowed. Please try again later."
                }
            )
        
        _rate_limit_storage[client_ip].append(now)
        response = await call_next(request)
        return response


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Request timeout middleware to prevent long-running requests"""
    
    def __init__(self, app: ASGIApp, timeout_seconds: int = 30):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
    
    async def dispatch(self, request: Request, call_next: Callable):
        import asyncio
        
        if request.url.path == "/health":
            return await call_next(request)
        
        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
            return response
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "message": "Request timeout",
                    "detail": f"Request took longer than {self.timeout_seconds} seconds to process. Please try again with a simpler request."
                }
            )


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Input validation middleware to prevent injection attacks"""
    
    SQL_INJECTION_PATTERNS = [
        r"(?i)(union\s+select|select\s+.*\s+from|insert\s+into|delete\s+from|drop\s+table)",
        r"(?i)(or\s+1\s*=\s*1|or\s+'1'\s*=\s*'1')",
        r"(?i)(exec\s*\(|execute\s*\()",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
    ]
    
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"^\.\.$",  # Match standalone ".."
    ]
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.sql_patterns = [re.compile(pattern) for pattern in self.SQL_INJECTION_PATTERNS]
        self.xss_patterns = [re.compile(pattern) for pattern in self.XSS_PATTERNS]
        self.path_patterns = [re.compile(pattern) for pattern in self.PATH_TRAVERSAL_PATTERNS]
    
    def _check_for_malicious_input(self, value: str) -> bool:
        """Check if input contains potentially malicious patterns"""
        if not isinstance(value, str):
            return False
        
        value_lower = value.lower()
        
        # Check SQL injection patterns
        for pattern in self.sql_patterns:
            if pattern.search(value_lower):
                return True
        
        # Check XSS patterns
        for pattern in self.xss_patterns:
            if pattern.search(value_lower):
                return True
        
        # Check path traversal patterns
        for pattern in self.path_patterns:
            if pattern.search(value_lower):
                return True
        
        return False
    
    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        for param_name, param_value in request.query_params.items():
            if isinstance(param_value, str) and self._check_for_malicious_input(param_value):
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": "Invalid input detected",
                        "detail": f"Query parameter '{param_name}' contains potentially malicious content."
                    }
                )
        
        path_parts = request.url.path.split("/")
        for part in path_parts:
            if self._check_for_malicious_input(part):
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": "Invalid input detected",
                        "detail": "URL path contains potentially malicious content."
                    }
                )
        
        response = await call_next(request)
        return response

