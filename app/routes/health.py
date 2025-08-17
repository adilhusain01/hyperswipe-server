"""
Health check and monitoring routes
"""
from fastapi import APIRouter
from app.models import HealthResponse
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Get the current health status of the signing service"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns the current status of the service including:
    - Service health status
    - Version information  
    - Environment configuration
    - Hyperliquid connection status
    """
    try:
        # TODO: Add actual health checks here
        # - Database connectivity
        # - Hyperliquid API accessibility
        # - Memory/CPU usage
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            environment=settings.environment,
            hyperliquid_testnet=settings.hyperliquid_testnet
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            version="1.0.0", 
            environment=settings.environment,
            hyperliquid_testnet=settings.hyperliquid_testnet
        )


@router.get(
    "/status",
    summary="Service Status",
    description="Detailed service status information"
)
async def service_status() -> dict:
    """
    Detailed service status for debugging and monitoring.
    """
    return {
        "service": "HyperSwipe Signing Service",
        "version": "1.0.0",
        "environment": settings.environment,
        "configuration": {
            "hyperliquid_testnet": settings.hyperliquid_testnet,
            "hyperliquid_base_url": settings.hyperliquid_base_url,
            "cors_origins": settings.cors_origins,
            "rate_limit_per_minute": settings.rate_limit_per_minute
        },
        "status": "operational"
    }

