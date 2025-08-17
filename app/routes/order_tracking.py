"""
Order Tracking API routes
Provides monitoring and control endpoints for the order tracking service
"""
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, Dict, Any
from app.services.order_tracking_service import get_order_tracking_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tracking", tags=["order-tracking"])

@router.get(
    "/status",
    summary="Get Order Tracking Status",
    description="Get the current status and statistics of the order tracking service"
)
async def get_tracking_status() -> Dict[str, Any]:
    """Get order tracking service status and statistics"""
    try:
        service = get_order_tracking_service()
        
        if not service:
            return {
                "status": "not_initialized",
                "message": "Order tracking service not initialized"
            }
        
        stats = service.get_statistics()
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting tracking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tracking status: {str(e)}"
        )

@router.get(
    "/orders/{order_id}",
    summary="Get Order Details",
    description="Get detailed tracking information for a specific order"
)
async def get_order_details(order_id: str) -> Dict[str, Any]:
    """Get detailed information about a tracked order"""
    try:
        service = get_order_tracking_service()
        
        if not service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Order tracking service not available"
            )
        
        order_details = service.get_order_details(order_id)
        
        if not order_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found in tracking system"
            )
        
        return {
            "success": True,
            "data": order_details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order details for {order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order details: {str(e)}"
        )

@router.post(
    "/orders/{order_id}/stop",
    summary="Stop Tracking Order",
    description="Stop tracking a specific order"
)
async def stop_tracking_order(
    order_id: str,
    reason: Optional[str] = Query(None, description="Reason for stopping tracking")
) -> Dict[str, Any]:
    """Stop tracking a specific order"""
    try:
        service = get_order_tracking_service()
        
        if not service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Order tracking service not available"
            )
        
        success = await service.stop_tracking_order(order_id, reason or "Manual stop via API")
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found or already stopped"
            )
        
        return {
            "success": True,
            "message": f"Stopped tracking order {order_id}",
            "reason": reason or "Manual stop via API"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping tracking for order {order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop tracking: {str(e)}"
        )

@router.get(
    "/health",
    summary="Order Tracking Health Check",
    description="Check the health of the order tracking service components"
)
async def tracking_health_check() -> Dict[str, Any]:
    """Health check for order tracking service"""
    try:
        service = get_order_tracking_service()
        
        if not service:
            return {
                "status": "unhealthy",
                "reason": "Service not initialized",
                "components": {
                    "service": "not_initialized",
                    "api_client": "unknown",
                    "tracker": "unknown"
                }
            }
        
        if not service.is_running:
            return {
                "status": "unhealthy",
                "reason": "Service not running",
                "components": {
                    "service": "stopped",
                    "api_client": "unknown",
                    "tracker": "unknown"
                }
            }
        
        # Get component health
        stats = service.get_statistics()
        api_stats = stats.get('api_client_stats', {})
        tracker_stats = stats.get('tracker_stats', {})
        
        # Determine overall health
        api_health = "healthy" if api_stats.get('session_active', False) else "unhealthy"
        tracker_health = "healthy" if tracker_stats.get('active_orders', 0) >= 0 else "unhealthy"
        
        overall_status = "healthy" if api_health == "healthy" and tracker_health == "healthy" else "degraded"
        
        return {
            "status": overall_status,
            "components": {
                "service": "running",
                "api_client": api_health,
                "tracker": tracker_health
            },
            "statistics": {
                "active_orders": tracker_stats.get('active_orders', 0),
                "total_orders_tracked": tracker_stats.get('orders_tracked', 0),
                "notifications_sent": tracker_stats.get('notifications_sent', 0),
                "api_circuit_breaker": api_stats.get('circuit_breaker', {}).get('state', 'unknown')
            }
        }
        
    except Exception as e:
        logger.error(f"Error in tracking health check: {e}")
        return {
            "status": "unhealthy",
            "reason": f"Health check failed: {str(e)}",
            "components": {
                "service": "error",
                "api_client": "error",
                "tracker": "error"
            }
        }