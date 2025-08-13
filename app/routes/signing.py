"""
Signing API routes
"""
from fastapi import APIRouter, HTTPException, status
from app.models import OrderRequest, SignatureResponse, ErrorResponse
from app.services.hyperliquid_signer import HyperliquidSigner
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["signing"])

# Initialize the signer
signer = HyperliquidSigner(is_testnet=settings.hyperliquid_testnet)


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
            
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
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