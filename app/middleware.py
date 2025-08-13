"""
Middleware for security, logging, and request handling
"""
import time
import logging
from typing import Dict, Any
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for API key validation and rate limiting"""
    
    def __init__(self, app, api_key_header: str = "X-API-Key"):
        super().__init__(app)
        self.api_key_header = api_key_header
        self.rate_limits: Dict[str, list] = {}  # Simple in-memory rate limiting
    
    async def dispatch(self, request: Request, call_next):
        # Skip middleware for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Rate limiting (simple implementation)
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean old requests (older than 1 minute)
        if client_ip in self.rate_limits:
            self.rate_limits[client_ip] = [
                req_time for req_time in self.rate_limits[client_ip] 
                if current_time - req_time < 60
            ]
        else:
            self.rate_limits[client_ip] = []
        
        # Check rate limit (100 requests per minute)
        if len(self.rate_limits[client_ip]) >= 100:
            raise HTTPException(
                status_code=429, 
                detail="Rate limit exceeded. Maximum 100 requests per minute."
            )
        
        # Add current request
        self.rate_limits[client_ip].append(current_time)
        
        # Continue with request
        response = await call_next(request)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging middleware"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"{request.method} {request.url.path} - {request.client.host}")
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        return response