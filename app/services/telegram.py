"""
Telegram notification service for HyperSwipe
Professional trading alerts via Telegram bot
"""
import json
import logging
import asyncio
from typing import Optional
import aiohttp
from app.models.database import TelegramUser, NotificationSettings, TradingStats

logger = logging.getLogger(__name__)

class TelegramService:
    """Professional Telegram notification service for trading alerts"""
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.session = None
        
    async def start(self):
        """Initialize the Telegram service"""
        self.session = aiohttp.ClientSession()
        logger.info("🤖 Telegram service started")
        
    async def stop(self):
        """Cleanup the Telegram service"""
        if self.session:
            await self.session.close()
        logger.info("🤖 Telegram service stopped")
    
    async def send_message(self, chat_id: str, text: str, parse_mode: Optional[str] = "Markdown", reply_markup: Optional[dict] = None):
        """Send a message to a Telegram chat"""
        if not self.session:
            logger.error("❌ Telegram service not started")
            return False
            
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text
            }
            
            if parse_mode:
                payload["parse_mode"] = parse_mode
            
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"📱 Message sent to {chat_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send message: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {e}")
            return False
    
    async def register_user(self, wallet_address: str, chat_id: str, username: str = None, first_name: str = None):
        """Register a user's Telegram chat ID with their wallet address"""
        try:
            # Check if user already exists
            existing_user = await TelegramUser.get_by_wallet(wallet_address)
            
            if existing_user:
                # Update existing user
                existing_user.chat_id = chat_id
                existing_user.username = username
                existing_user.first_name = first_name
                await existing_user.update_last_seen()
                logger.info(f"👤 Updated Telegram user: {wallet_address} -> {chat_id}")
            else:
                # Create new user
                user = TelegramUser(
                    wallet_address=wallet_address.lower(),
                    chat_id=chat_id,
                    username=username,
                    first_name=first_name
                )
                await user.insert()
                logger.info(f"👤 Registered new Telegram user: {wallet_address} -> {chat_id}")
                
                # Create default notification settings
                settings = await NotificationSettings.get_or_create(wallet_address)
                
                # Initialize trading stats
                stats = await TradingStats.get_or_create(wallet_address)
                
        except Exception as e:
            logger.error(f"❌ Error registering user: {e}")
            raise
    
    async def get_user_chat_id(self, wallet_address: str) -> Optional[str]:
        """Get the Telegram chat ID for a wallet address"""
        try:
            user = await TelegramUser.get_by_wallet(wallet_address)
            return user.chat_id if user else None
        except Exception as e:
            logger.error(f"❌ Error getting user chat ID: {e}")
            return None
    
    async def unlink_user(self, wallet_address: str) -> bool:
        """Unlink a user's Telegram account"""
        try:
            user = await TelegramUser.get_by_wallet(wallet_address)
            if user:
                user.is_active = False
                await user.save()
                logger.info(f"🚫 Unlinked Telegram user: {wallet_address}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error unlinking user: {e}")
            return False
    
    async def send_pnl_alert(self, wallet_address: str, position_data: dict):
        """Send a PnL alert to the user"""
        chat_id = await self.get_user_chat_id(wallet_address)
        if not chat_id:
            logger.warning(f"⚠️ No Telegram chat ID for wallet {wallet_address}")
            return False
        
        # Extract position data
        coin = position_data.get('coin', 'Unknown')
        side = "Long 📈" if float(position_data.get('szi', 0)) > 0 else "Short 📉"
        entry_price = float(position_data.get('entryPx', 0))
        current_price = float(position_data.get('markPrice', entry_price))
        unrealized_pnl = float(position_data.get('unrealizedPnl', 0))
        size = abs(float(position_data.get('szi', 0)))
        
        # Calculate percentage change
        pnl_percentage = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        if float(position_data.get('szi', 0)) < 0:  # Short position
            pnl_percentage = -pnl_percentage
        
        # Determine alert emoji based on PnL
        if unrealized_pnl > 0:
            status_emoji = "🚀" if pnl_percentage > 10 else "📈"
        else:
            status_emoji = "🔥" if pnl_percentage < -10 else "📉"
        
        # Format the message
        message = f"""{status_emoji} **{coin}/USD {side}**

📊 **Position Update**
• Entry: ${entry_price:,.4f}
• Current: ${current_price:,.4f}
• Change: {pnl_percentage:+.2f}%

💰 **P&L Summary**
• Unrealized: {"+" if unrealized_pnl >= 0 else ""}${unrealized_pnl:,.2f}
• Size: {size:.4f} {coin}

⏰ {self._get_timestamp()}"""
        
        # Add action buttons for significant moves
        buttons = None
        if abs(pnl_percentage) > 5:  # Show actions for >5% moves
            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "📈 View Chart", "url": f"https://app.hyperswipe.rizzmo.site"},
                        {"text": "⚡ Close Position", "callback_data": f"close_{coin}"}
                    ]
                ]
            }
        
        return await self.send_message(chat_id, message, reply_markup=buttons)
    
    async def send_position_fill_alert(self, wallet_address: str, fill_data: dict):
        """Send position fill notification"""
        chat_id = await self.get_user_chat_id(wallet_address)
        if not chat_id:
            return False
        
        coin = fill_data.get('coin', 'Unknown')
        side = "Buy 📈" if fill_data.get('side') == 'B' else "Sell 📉"
        price = float(fill_data.get('px', 0))
        size = float(fill_data.get('sz', 0))
        fee = float(fill_data.get('fee', 0))
        
        message = f"""✅ **Order Filled!**

🎯 **{coin}/USD {side}**
• Price: ${price:,.4f}
• Size: {size:.4f} {coin}
• Fee: ${fee:.4f}

⏰ {self._get_timestamp()}"""
        
        return await self.send_message(chat_id, message)
    
    async def send_liquidation_warning(self, wallet_address: str, margin_ratio: float):
        """Send liquidation warning"""
        chat_id = await self.get_user_chat_id(wallet_address)
        if not chat_id:
            return False
        
        message = f"""🚨 **LIQUIDATION WARNING**

⚠️ **Low Margin Ratio: {margin_ratio:.1f}%**

Your positions are at risk of liquidation!
Consider:
• Adding more margin
• Closing some positions
• Reducing position sizes

⏰ {self._get_timestamp()}"""
        
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🏃 View Positions", "url": "https://app.hyperswipe.rizzmo.site"},
                    {"text": "💰 Add Margin", "callback_data": "add_margin"}
                ]
            ]
        }
        
        return await self.send_message(chat_id, message, reply_markup=buttons)
    
    async def send_welcome_message(self, chat_id: str, wallet_address: str):
        """Send welcome message to new user"""
        message = f"""🎉 **Welcome to HyperSwipe Alerts!**

Your wallet **{wallet_address[:6]}...{wallet_address[-4:]}** is now connected!

You'll receive notifications for:
📈 Position updates & P&L alerts
💰 Order fills & executions  
⚠️ Risk management warnings
📊 Daily portfolio summaries

🚀 **Happy trading!**"""
        
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "📱 Open HyperSwipe", "url": "https://app.hyperswipe.rizzmo.site"}
                ]
            ]
        }
        
        return await self.send_message(chat_id, message, reply_markup=buttons)
    
    def _get_timestamp(self) -> str:
        """Get formatted timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S UTC")

# Global Telegram service instance
telegram_service: Optional[TelegramService] = None

def get_telegram_service() -> Optional[TelegramService]:
    """Get the global Telegram service instance"""
    return telegram_service

async def initialize_telegram_service(bot_token: str):
    """Initialize the global Telegram service"""
    global telegram_service
    if bot_token:
        telegram_service = TelegramService(bot_token)
        await telegram_service.start()
        logger.info("🤖 Telegram service initialized")
    else:
        logger.warning("⚠️ No Telegram bot token provided")

async def cleanup_telegram_service():
    """Cleanup the global Telegram service"""
    global telegram_service
    if telegram_service:
        await telegram_service.stop()
        telegram_service = None