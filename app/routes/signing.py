"""
Signing API routes with industry-grade order tracking
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError
from app.models import OrderRequest, CancelOrderRequest, SignatureResponse, ErrorResponse
from app.services.hyperliquid_signer import HyperliquidSigner
from app.config import settings
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["signing"])

# Initialize the signer
signer = HyperliquidSigner(is_testnet=settings.hyperliquid_testnet)

# Global order tracking service - will be initialized in main.py
order_tracking_service = None

def set_order_tracking_service(service):
    """Set the global order tracking service"""
    global order_tracking_service
    order_tracking_service = service

async def _start_order_tracking(order_request: OrderRequest, signing_result: dict):
    """Start tracking a newly signed order"""
    try:
        from app.services.order_state_machine import OrderContext, OrderEvent
        
        # Generate a unique tracking ID
        tracking_id = str(uuid.uuid4())
        
        # Extract order data from signing result
        order_data = signing_result.get("order_request", {})
        exchange_order_id = None  # Will be updated when we get userEvents
        
        # Get nonce which can help us correlate with future fills
        nonce = order_data.get("nonce")
        
        # Extract action details for better tracking
        action = order_data.get("action", {})
        order_action = action.get("order", {}) if isinstance(action, dict) else {}
        
        # Create order context
        order_context = OrderContext(
            order_id=tracking_id,
            user_address=order_request.wallet_address.lower(),
            asset_index=order_request.asset_index,
            is_buy=order_request.is_buy,
            price=float(order_request.price),
            size=float(order_request.size),
            order_type=order_request.order_type,
            time_in_force=order_request.time_in_force,
            submitted_at=datetime.utcnow(),
            exchange_order_id=exchange_order_id,
            metadata={
                'tracking_id': tracking_id,
                'state': 'pending',
                'signing_result': signing_result,
                'vault_address': order_request.vault_address,
                'nonce': nonce,
                'action': action,
                'order_action': order_action
            }
        )
        
        # Start tracking
        success = await order_tracking_service.track_order(tracking_id, order_context)
        
        if success:
            logger.info(f"Started tracking order {tracking_id} for {order_request.wallet_address}")
            
            # Trigger submission event since order was successfully signed
            await order_tracking_service.state_machine.trigger_event(
                tracking_id,
                OrderEvent.SUBMIT,
                {
                    'exchange_order_id': exchange_order_id,
                    'signing_timestamp': datetime.utcnow().isoformat(),
                    'source': 'signing_endpoint'
                }
            )
        else:
            logger.error(f"Failed to start tracking order {tracking_id}")
            
    except Exception as e:
        logger.error(f"Error starting order tracking: {e}")
        # Don't fail the signing request if tracking fails


@router.post(
    "/sign-order",
    response_model=SignatureResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Signing failed"}
    },
    summary="Sign Hyperliquid Order",
    description="Signs a Hyperliquid perpetual order using the official Python SDK"
)
async def sign_order(order_request: OrderRequest) -> SignatureResponse:
    """
    Sign a Hyperliquid order transaction.
    
    This endpoint accepts order parameters and returns a signed transaction
    that can be submitted directly to the Hyperliquid exchange API.
    """
    try:
        logger.info(f"Signing order for wallet: {order_request.wallet_address}")
        logger.debug(f"Order details: asset={order_request.asset_index}, "
                    f"is_buy={order_request.is_buy}, price={order_request.price}, "
                    f"size={order_request.size}")
        
        # Sign the order
        result = signer.sign_order(order_request)
        
        if result["success"]:
            logger.info(f"Order signed successfully for {order_request.wallet_address}")
            
            # Start order tracking if service is available
            if order_tracking_service:
                await _start_order_tracking(order_request, result)
            else:
                logger.warning("Order tracking service not available - tracking disabled")
            
            return SignatureResponse(
                success=True,
                signature=result["signature"],
                order_request=result["order_request"]
            )
        else:
            logger.error(f"Signing failed: {result['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Signing failed: {result['error']}"
            )
            
    except ValidationError as e:
        logger.error(f"Pydantic validation error: {str(e)}")
        error_details = []
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error['loc'])
            error_details.append(f"{field}: {error['msg']} (got: {error.get('input', 'N/A')})")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation failed: {'; '.join(error_details)}"
        )
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/verify-signature",
    summary="Verify Signature",
    description="Verify that a signature is valid for given order parameters"
)
async def verify_signature(
    action: dict,
    signature: dict,
    wallet_address: str,
    nonce: int,
    vault_address: str = None
) -> dict:
    """
    Verify a signature for debugging purposes.
    """
    try:
        is_valid = signer.verify_signature(
            action=action,
            signature=signature,
            wallet_address=wallet_address,
            nonce=nonce,
            vault_address=vault_address
        )
        
        return {
            "success": True,
            "valid": is_valid,
            "wallet_address": wallet_address
        }
        
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.post(
    "/cancel-order",
    response_model=SignatureResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Signing failed"}
    },
    summary="Cancel Hyperliquid Order",
    description="Signs a cancel order request using the official Python SDK"
)
async def cancel_order(cancel_request: CancelOrderRequest) -> SignatureResponse:
    """
    Cancel a Hyperliquid order.
    
    This endpoint accepts cancel parameters and returns a signed transaction
    that can be submitted directly to the Hyperliquid exchange API.
    """
    try:
        logger.info(f"Cancelling order for wallet: {cancel_request.wallet_address}")
        logger.debug(f"Cancel details: asset={cancel_request.asset_index}, "
                    f"order_id={cancel_request.order_id}")
        
        # Sign the cancel order
        result = signer.sign_cancel_order(cancel_request)
        
        if result["success"]:
            logger.info(f"Cancel order signed successfully for {cancel_request.wallet_address}")
            return SignatureResponse(
                success=True,
                signature=result["signature"],
                order_request=result["order_request"]
            )
        else:
            logger.error(f"Cancel signing failed: {result['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Cancel signing failed: {result['error']}"
            )
            
    except ValidationError as e:
        logger.error(f"Cancel Pydantic validation error: {str(e)}")
        error_details = []
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error['loc'])
            error_details.append(f"{field}: {error['msg']} (got: {error.get('input', 'N/A')})")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cancel validation failed: {'; '.join(error_details)}"
        )
    except ValueError as e:
        logger.error(f"Cancel validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cancel request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Cancel unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cancel internal server error: {str(e)}"
        )