"""
Telegram integration routes for HyperSwipe
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.services.telegram import get_telegram_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

class TelegramLinkRequest(BaseModel):
    wallet_address: str
    chat_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None

class TelegramTestRequest(BaseModel):
    wallet_address: str
    message_type: str = "welcome"  # welcome, pnl_alert, fill, liquidation_warning, daily_portfolio

@router.post("/link")
async def link_telegram_account(request: TelegramLinkRequest):
    """Link a wallet address to a Telegram chat ID"""
    try:
        telegram_service = get_telegram_service()
        if not telegram_service:
            raise HTTPException(
                status_code=503,
                detail="Telegram service not available"
            )
        
        # Register the user
        await telegram_service.register_user(
            wallet_address=request.wallet_address,
            chat_id=request.chat_id,
            username=request.username,
            first_name=request.first_name
        )
        
        # Send welcome message
        await telegram_service.send_welcome_message(
            chat_id=request.chat_id,
            wallet_address=request.wallet_address
        )
        
        logger.info(f"🤖 Linked Telegram account: {request.wallet_address} -> {request.chat_id}")
        
        return {
            "success": True,
            "message": "Telegram account linked successfully",
            "wallet_address": request.wallet_address,
            "chat_id": request.chat_id
        }
        
    except Exception as e:
        logger.error(f"❌ Error linking Telegram account: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to link Telegram account: {str(e)}"
        )

@router.post("/test")
async def test_telegram_notification(request: TelegramTestRequest):
    """Test Telegram notifications for a wallet address"""
    try:
        telegram_service = get_telegram_service()
        if not telegram_service:
            raise HTTPException(
                status_code=503,
                detail="Telegram service not available"
            )
        
        chat_id = await telegram_service.get_user_chat_id(request.wallet_address)
        if not chat_id:
            raise HTTPException(
                status_code=404,
                detail="Telegram account not linked for this wallet"
            )
        
        # Send test notification based on type
        if request.message_type == "welcome":
            success = await telegram_service.send_welcome_message(chat_id, request.wallet_address)
        elif request.message_type == "pnl_alert":
            # Mock position data for testing
            mock_position = {
                "coin": "SOL",
                "szi": "1.5",  # Long position
                "entryPx": "142.50",
                "markPrice": "156.20",
                "unrealizedPnl": "20.55"
            }
            success = await telegram_service.send_pnl_alert(request.wallet_address, mock_position)
        elif request.message_type == "fill":
            # Mock fill data for testing
            mock_fill = {
                "coin": "ETH",
                "side": "B",  # Buy
                "px": "2450.50",
                "sz": "0.25",
                "fee": "1.22"
            }
            success = await telegram_service.send_position_fill_alert(request.wallet_address, mock_fill)
        elif request.message_type == "liquidation_warning":
            success = await telegram_service.send_liquidation_warning(request.wallet_address, 15.2)
        elif request.message_type == "daily_portfolio":
            # Mock portfolio data for testing
            mock_portfolio = {
                "accountValue": "15420.75",
                "totalPnl": "125.80",
                "openPositions": [
                    {"coin": "BTC", "size": 0.05, "unrealizedPnl": 45.20},
                    {"coin": "ETH", "size": 2.5, "unrealizedPnl": -12.30},
                    {"coin": "SOL", "size": 15.0, "unrealizedPnl": 92.90}
                ],
                "dailyVolume": "8750.25",
                "tradesCount": 12
            }
            success = await telegram_service.send_daily_portfolio_summary(request.wallet_address, mock_portfolio)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid message type"
            )
        
        if success:
            return {
                "success": True,
                "message": f"Test {request.message_type} notification sent successfully"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send test notification"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error sending test notification: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test notification: {str(e)}"
        )

@router.get("/status/{wallet_address}")
async def get_telegram_status(wallet_address: str):
    """Get Telegram linking status for a wallet address"""
    try:
        telegram_service = get_telegram_service()
        if not telegram_service:
            return {
                "linked": False,
                "reason": "Telegram service not available"
            }
        
        chat_id = await telegram_service.get_user_chat_id(wallet_address)
        
        return {
            "linked": bool(chat_id),
            "wallet_address": wallet_address,
            "chat_id": chat_id if chat_id else None
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking Telegram status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check Telegram status: {str(e)}"
        )

@router.delete("/unlink/{wallet_address}")
async def unlink_telegram_account(wallet_address: str):
    """Unlink a Telegram account from a wallet address"""
    try:
        telegram_service = get_telegram_service()
        if not telegram_service:
            raise HTTPException(
                status_code=503,
                detail="Telegram service not available"
            )
        
        # Remove the user mapping
        success = await telegram_service.unlink_user(wallet_address)
        if success:
            return {
                "success": True,
                "message": "Telegram account unlinked successfully",
                "wallet_address": wallet_address
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Telegram account not found for this wallet"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error unlinking Telegram account: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unlink Telegram account: {str(e)}"
        )

@router.post("/webhook")
async def telegram_webhook(request: dict):
    """Webhook endpoint to receive Telegram updates"""
    try:
        telegram_service = get_telegram_service()
        if not telegram_service:
            logger.warning("⚠️ Telegram service not available for webhook")
            return {"ok": True}
        
        # Handle incoming message
        if "message" in request:
            message = request["message"]
            chat_id = str(message["chat"]["id"])
            text = message.get("text", "")
            user = message.get("from", {})
            
            logger.info(f"📨 Received message from {chat_id}: {text}")
            
            # Handle /start command - provide Chat ID for linking
            if text.startswith("/start"):
                first_name = user.get("first_name", "User")
                
                response_message = f"""🚀 Welcome to HyperSwipe Alerts!

Hi {first_name}! 👋

Your Chat ID is: {chat_id}

📋 Setup Instructions:
1. Copy the Chat ID above
2. Go to HyperSwipe app
3. Navigate to Settings > Telegram
4. Paste your Chat ID in the field
5. Click "Connect Telegram"

Once connected, you'll receive:
📈 Real-time position updates
💰 Order fill notifications  
⚠️ Risk management alerts
📊 Portfolio summaries

🚀 Ready to start trading?"""
                
                buttons = {
                    "inline_keyboard": [
                        [
                            {"text": "📱 Open HyperSwipe", "url": "https://app.hyperswipe.rizzmo.site"}
                        ]
                    ]
                }
                
                await telegram_service.send_message(chat_id, response_message, parse_mode=None, reply_markup=buttons)
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        return {"ok": True}  # Always return ok to Telegram