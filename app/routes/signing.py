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

def _get_asset_name(asset_index: int) -> str:
    """Map asset index to coin name - Complete testnet mappings from API"""
    # Complete Hyperliquid testnet asset mappings from /info meta API
    asset_map = {
        0: "SOL", 1: "APT", 2: "ATOM", 3: "BTC", 4: "ETH", 5: "MATIC", 6: "BNB", 7: "AVAX", 8: "GMT", 9: "DYDX",
        10: "APE", 11: "OP", 12: "kPEPE", 13: "ARB", 14: "RLB", 15: "WLD", 16: "HPOS", 17: "UNIBOT", 18: "COMP", 19: "FXS",
        20: "MKR", 21: "AAVE", 22: "SNX", 23: "RNDR", 24: "LDO", 25: "SUI", 26: "INJ", 27: "STX", 28: "FTM", 29: "kSHIB",
        30: "OX", 31: "FRIEND", 32: "ZRO", 33: "BLZ", 34: "BANANA", 35: "FTT", 36: "TRB", 37: "CANTO", 38: "BIGTIME", 39: "NTRN",
        40: "KAS", 41: "BLUR", 42: "TIA", 43: "BSV", 44: "TON", 45: "ADA", 46: "MINA", 47: "POLYX", 48: "GAS", 49: "AXL",
        50: "PENDLE", 51: "STG", 52: "FET", 53: "STRAX", 54: "NEAR", 55: "MEME", 56: "ORDI", 57: "BADGER", 58: "NEO", 59: "ZEN",
        60: "FIL", 61: "PYTH", 62: "RUNE", 63: "SUSHI", 64: "ILV", 65: "MAV", 66: "IMX", 67: "kBONK", 68: "NFTI", 69: "SUPER",
        70: "USTC", 71: "JUP", 72: "JOE", 73: "GALA", 74: "RSR", 75: "kLUNC", 76: "JTO", 77: "ACE", 78: "WIF", 79: "CAKE",
        80: "PEOPLE", 81: "ENS", 82: "ETC", 83: "XAI", 84: "MANTA", 85: "UMA", 86: "REQ", 87: "ONDO", 88: "ALT", 89: "ZETA",
        90: "DYM", 91: "MAVIA", 92: "W", 93: "PANDORA", 94: "AI", 95: "TAO", 96: "PIXEL", 97: "AR", 98: "TNSR", 99: "SAGA",
        100: "MERL", 101: "HBAR", 102: "POPCAT", 103: "OMNI", 104: "EIGEN", 105: "REZ", 106: "NOT", 107: "TURBO", 108: "IO", 109: "BRETT",
        110: "ZK", 111: "BLAST", 112: "LISTA", 113: "MEW", 114: "RENDER", 115: "kDOGS", 116: "POL", 117: "CATI", 118: "CELO", 119: "HMSTR",
        120: "SCR", 121: "NEIROETH", 122: "kNEIRO", 123: "GOAT", 124: "MOODENG", 125: "PURR", 126: "GRASS", 127: "PNUT", 128: "XLM", 129: "CHILLGUY",
        130: "SAND", 131: "ALGO", 132: "ICP", 133: "IOTA", 134: "VET", 135: "HYPE", 136: "ME", 137: "MOVE", 138: "VIRTUAL", 139: "PENGU",
        140: "USUAL", 141: "FARTCOIN", 142: "AIXBT", 143: "AI16Z", 144: "ZEREBRO", 145: "BIO", 146: "SPX", 147: "GRIFFAIN", 148: "S", 149: "MORPHO",
        150: "TRUMP", 151: "ANIME", 152: "MELANIA", 153: "VINE", 154: "VVV", 155: "JELLYJELLY", 156: "JELLY", 157: "BERA", 158: "TST", 159: "LAYER",
        160: "IP", 161: "OM", 162: "KAITO", 163: "CHZ", 164: "NIL", 165: "PAXG", 166: "PROMPT", 167: "BABY", 168: "WCT", 169: "HYPER",
        170: "ZORA", 171: "INIT", 172: "DOOD", 173: "DOGE", 174: "LAUNCHCOIN", 175: "NXPC", 176: "SOPH", 177: "RESOLV", 178: "SYRUP", 179: "PUMP",
        180: "PROVE"
    }
    return asset_map.get(asset_index, f"Asset_{asset_index}")

async def _send_order_placed_notification(order_request: OrderRequest, signing_result: dict):
    """Send Telegram notification when an order is successfully placed"""
    try:
        from app.services.telegram import get_telegram_service
        
        telegram_service = get_telegram_service()
        if not telegram_service:
            logger.debug("Telegram service not available for order placed notification")
            return
        
        user_address = order_request.wallet_address.lower()
        
        # Check if user has Telegram notifications enabled
        chat_id = await telegram_service.get_user_chat_id(user_address)
        if not chat_id:
            logger.debug(f"No Telegram chat ID for {user_address} - skipping order placed notification")
            return
        
        # Get user notification settings
        from app.models.database import NotificationSettings
        notification_settings = await NotificationSettings.get_or_create(user_address)
        
        # Check if order notifications are enabled (assuming we want this under fill_notifications)
        if not notification_settings.fill_notifications:
            logger.debug(f"Fill notifications disabled for {user_address} - skipping order placed notification")
            return
        
        # Calculate order value to check against minimum threshold
        order_value = float(order_request.price) * float(order_request.size)
        
        if order_value < notification_settings.min_notification_amount:
            logger.debug(f"Order value ${order_value:.2f} below threshold ${notification_settings.min_notification_amount} for {user_address}")
            return
        
        # Create order placed notification
        side = "Buy" if order_request.is_buy else "Sell"
        asset_name = _get_asset_name(order_request.asset_index)
        
        message = f"""📋 **Order Placed Successfully!**

🎯 **{asset_name} {side} Order**
• Price: ${float(order_request.price):,.4f}
• Size: {float(order_request.size):.4f}
• Total Value: ${order_value:,.2f}

🔄 **Order Details**
• Type: {order_request.order_type.title()}
• Time in Force: {order_request.time_in_force}
• Reduce Only: {'Yes' if order_request.reduce_only else 'No'}

📡 You'll receive updates when this order is filled.

⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"""

        await telegram_service.send_message(chat_id, message)
        
        # Record notification in stats
        from app.models.database import TradingStats
        trading_stats = await TradingStats.get_or_create(user_address)
        await trading_stats.record_notification()
        
        logger.info(f"✅ Sent order placed notification for {user_address}: {asset_name} {side} {order_request.size}@${order_request.price}")
        
    except Exception as e:
        logger.error(f"❌ Error sending order placed notification: {e}")
        # Don't fail the order placement if notification fails

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