"""
Unit tests for middleware
"""
import pytest
import json
from datetime import datetime, timedelta
from fastapi import Request
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.core.middleware import (
    RateLimitMiddleware,
    RequestTimeoutMiddleware,
    InputValidationMiddleware
)


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware"""
    
    def test_rate_limit_allows_requests_within_limit(self, client):
        """Test that requests within limit are allowed"""
        app = client.app
        middleware = RateLimitMiddleware(app, requests_per_minute=10, requests_per_hour=100)
        
        # Make 5 requests (within limit)
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
    
    def test_rate_limit_blocks_excessive_requests(self, client):
        """Test that excessive requests are blocked"""
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from app.core.middleware import _rate_limit_storage
        
        # Clear rate limit storage to ensure clean test
        _rate_limit_storage.clear()
        
        # Create a test app with the middleware
        test_app = FastAPI()
        
        @test_app.get("/test")
        def test_endpoint():
            return JSONResponse(content={"status": "ok"})
        
        # Add middleware with low limits
        test_app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=2,
            requests_per_hour=10
        )
        
        test_client = TestClient(test_app)
        
        # Make 2 requests (at limit) - use /test endpoint (not /health which is skipped)
        test_client.get("/test")
        test_client.get("/test")
        
        # Third request should be blocked
        response = test_client.get("/test")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["message"]
    
    def test_rate_limit_skips_health_endpoint(self, client):
        """Test that health endpoint is not rate limited"""
        response = client.get("/health")
        assert response.status_code in [200, 503]  # May be 503 if DB not connected


class TestRequestTimeoutMiddleware:
    """Tests for RequestTimeoutMiddleware"""
    
    @pytest.mark.asyncio
    async def test_timeout_allows_fast_requests(self):
        """Test that fast requests are allowed"""
        from fastapi.responses import JSONResponse
        
        async def fast_handler(request):
            return JSONResponse(content={"status": "ok"})
        
        # Create a mock app for the middleware
        mock_app = MagicMock()
        middleware = RequestTimeoutMiddleware(mock_app, timeout_seconds=5)
        
        request = MagicMock(spec=Request)
        request.url.path = "/test"
        
        # Create a call_next that would be called
        async def call_next(req):
            return await fast_handler(req)
        
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200
        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_timeout_blocks_slow_requests(self):
        """Test that slow requests are timed out"""
        import asyncio
        from fastapi.responses import JSONResponse
        
        async def slow_handler(request):
            await asyncio.sleep(2)  # Simulate slow operation
            return JSONResponse(content={"status": "ok"})
        
        # Create a mock app for the middleware
        mock_app = MagicMock()
        middleware = RequestTimeoutMiddleware(mock_app, timeout_seconds=1)
        
        request = MagicMock(spec=Request)
        request.url.path = "/test"
        
        # Create a call_next that would be called (but will timeout)
        async def call_next(req):
            return await slow_handler(req)
        
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 504
        assert "timeout" in response.body.decode().lower()


class TestInputValidationMiddleware:
    """Tests for InputValidationMiddleware"""
    
    @pytest.mark.asyncio
    async def test_validates_query_parameters(self):
        """Test that malicious query parameters are blocked"""
        from fastapi.responses import JSONResponse
        
        async def handler(request):
            return JSONResponse(content={"status": "ok"})
        
        # Create a mock app for the middleware
        mock_app = MagicMock()
        middleware = InputValidationMiddleware(mock_app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/test"
        request.query_params = {"name": "test'; DROP TABLE users; --"}
        
        # Create a call_next that would be called if not blocked
        async def call_next(req):
            return await handler(req)
        
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        assert "Invalid input detected" in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_validates_path_parameters(self):
        """Test that malicious path parameters are blocked"""
        from fastapi.responses import JSONResponse
        
        async def handler(request):
            return JSONResponse(content={"status": "ok"})
        
        # Create a mock app for the middleware
        mock_app = MagicMock()
        middleware = InputValidationMiddleware(mock_app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/test/../../../etc/passwd"
        
        # Create a call_next that would be called if not blocked
        async def call_next(req):
            return await handler(req)
        
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 400
        assert "Invalid input detected" in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_allows_valid_input(self):
        """Test that valid input is allowed"""
        from fastapi.responses import JSONResponse
        
        async def handler(request):
            return JSONResponse(content={"status": "ok"})
        
        # Create a mock app for the middleware
        mock_app = MagicMock()
        middleware = InputValidationMiddleware(mock_app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/test"
        request.query_params = {"name": "John Doe"}
        
        # Create a call_next that would be called if not blocked
        async def call_next(req):
            return await handler(req)
        
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200
        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_skips_validation_for_docs(self):
        """Test that docs endpoints are skipped"""
        from fastapi.responses import JSONResponse
        
        async def handler(request):
            return JSONResponse(content={"status": "ok"})
        
        # Create a mock app for the middleware
        mock_app = MagicMock()
        middleware = InputValidationMiddleware(mock_app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/docs"
        request.query_params = {}
        
        # Create a call_next that would be called if not blocked
        async def call_next(req):
            return await handler(req)
        
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200
        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "ok"

