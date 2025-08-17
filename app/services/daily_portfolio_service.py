"""
Daily Portfolio Notification Service for HyperSwipe
Sends daily portfolio summaries to Telegram users
"""
import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Dict, Optional, Set
from app.services.hyperliquid_api_client import HyperliquidAPIClient
from app.models.database import TelegramUser, NotificationSettings, TradingStats

logger = logging.getLogger(__name__)

class DailyPortfolioService:
    """
    Service to send daily portfolio summaries via Telegram
    Runs once per day at a configured time (e.g., 9:00 AM UTC)
    """
    
    def __init__(self, hyperliquid_base_url: str, is_testnet: bool = True, notification_hour: int = 9):
        self.api_client = HyperliquidAPIClient(hyperliquid_base_url, is_testnet)
        self.notification_hour = notification_hour  # Hour of day to send (UTC)
        self.is_running = False
        self.daily_task: Optional[asyncio.Task] = None
        
        # Track last notification date per user to avoid duplicates
        self.last_notification_dates: Dict[str, str] = {}
        
        # Track registered users
        self.registered_users: Set[str] = set()
        
    async def start(self):
        """Start the daily portfolio service"""
        if self.is_running:
            logger.warning("Daily portfolio service already running")
            return
        
        try:
            # Start API client
            await self.api_client.start()
            
            # Refresh registered users
            await self._refresh_registered_users()
            
            # Start daily task
            self.daily_task = asyncio.create_task(self._daily_loop())
            self.is_running = True
            
            logger.info(f"📊 Daily portfolio service started (notification time: {self.notification_hour:02d}:00 UTC)")
            
        except Exception as e:
            logger.error(f"❌ Failed to start daily portfolio service: {e}")
            raise
    
    async def stop(self):
        """Stop the daily portfolio service"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.daily_task and not self.daily_task.done():
            self.daily_task.cancel()
            try:
                await self.daily_task
            except asyncio.CancelledError:
                pass
        
        await self.api_client.stop()
        logger.info("📊 Daily portfolio service stopped")
    
    async def _refresh_registered_users(self):
        """Refresh list of users with daily summary notifications enabled"""
        try:
            # Get all active Telegram users
            telegram_users = await TelegramUser.find({"is_active": True}).to_list()
            
            new_registered_users = set()
            for user in telegram_users:
                # Check if daily summary notifications are enabled
                settings = await NotificationSettings.get_or_create(user.wallet_address)
                if settings.daily_summary:
                    new_registered_users.add(user.wallet_address.lower())
            
            self.registered_users = new_registered_users
            logger.info(f"📋 Tracking daily summaries for {len(self.registered_users)} registered users")
            
        except Exception as e:
            logger.error(f"❌ Error refreshing registered users: {e}")
    
    async def _daily_loop(self):
        """Main daily loop for portfolio notifications"""
        logger.info("🔄 Starting daily portfolio notification loop")
        
        while self.is_running:
            try:
                # Calculate next notification time
                now = datetime.utcnow()
                next_notification = self._get_next_notification_time(now)
                
                # Calculate sleep duration
                sleep_seconds = (next_notification - now).total_seconds()
                
                if sleep_seconds > 0:
                    logger.info(f"⏰ Next daily portfolio notification scheduled for {next_notification.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    await asyncio.sleep(sleep_seconds)
                
                if not self.is_running:
                    break
                
                # Refresh users list
                await self._refresh_registered_users()
                
                # Send daily summaries
                await self._send_daily_summaries()
                
                # Sleep a bit to avoid running multiple times in the same minute
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("🛑 Daily portfolio loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in daily portfolio loop: {e}")
                # Sleep for an hour before retrying
                await asyncio.sleep(3600)
    
    def _get_next_notification_time(self, current_time: datetime) -> datetime:
        """Calculate the next notification time"""
        # Target time today
        target_time = current_time.replace(
            hour=self.notification_hour, 
            minute=0, 
            second=0, 
            microsecond=0
        )
        
        # If target time has passed today, schedule for tomorrow
        if current_time >= target_time:
            target_time += timedelta(days=1)
        
        return target_time
    
    async def _send_daily_summaries(self):
        """Send daily portfolio summaries to all registered users"""
        if not self.registered_users:
            logger.info("👥 No registered users for daily portfolio summaries")
            return
        
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        sent_count = 0
        
        logger.info(f"📊 Sending daily portfolio summaries to {len(self.registered_users)} users")
        
        for user_address in list(self.registered_users):
            try:
                # Check if we already sent summary today
                if self.last_notification_dates.get(user_address) == today_str:
                    logger.debug(f"📊 Daily summary already sent today for {user_address}")
                    continue
                
                # Get portfolio data and send summary
                success = await self._send_user_portfolio_summary(user_address)
                
                if success:
                    self.last_notification_dates[user_address] = today_str
                    sent_count += 1
                
                # Small delay between users to be nice to APIs
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error sending daily summary to {user_address}: {e}")
        
        logger.info(f"✅ Sent {sent_count} daily portfolio summaries")
    
    async def _send_user_portfolio_summary(self, user_address: str) -> bool:
        """Send portfolio summary for a specific user"""
        try:
            from app.services.telegram import get_telegram_service
            
            telegram_service = get_telegram_service()
            if not telegram_service:
                logger.warning("⚠️ Telegram service not available")
                return False
            
            # Check if user has Telegram notifications enabled
            chat_id = await telegram_service.get_user_chat_id(user_address)
            if not chat_id:
                logger.debug(f"🔍 No Telegram chat ID for {user_address}")
                return False
            
            # Get user state from Hyperliquid API
            success, user_state = await self.api_client.get_user_state(user_address)
            if not success:
                logger.warning(f"⚠️ Failed to get user state for {user_address}")
                return False
            
            # Get user fills from last 24 hours for daily stats
            yesterday = datetime.utcnow() - timedelta(days=1)
            fills_success, daily_fills = await self.api_client.get_user_fills(user_address, yesterday)
            
            # Calculate daily trading stats
            daily_volume = 0.0
            trades_count = 0
            daily_pnl = 0.0
            
            if fills_success and daily_fills:
                trades_count = len(daily_fills)
                for fill in daily_fills:
                    px = float(fill.get('px', 0))
                    sz = float(fill.get('sz', 0))
                    closed_pnl = float(fill.get('closedPnl', 0))
                    daily_volume += px * sz
                    daily_pnl += closed_pnl
            
            # Extract account data
            margin_summary = user_state.get('marginSummary', {})
            asset_positions = user_state.get('assetPositions', [])
            
            # Prepare open positions data
            open_positions = []
            for position in asset_positions:
                if isinstance(position, dict) and 'position' in position:
                    pos_data = position['position']
                    size = abs(float(pos_data.get('szi', 0)))
                    if size > 0:  # Only include open positions
                        open_positions.append({
                            'coin': pos_data.get('coin', 'Unknown'),
                            'size': size,
                            'unrealizedPnl': float(pos_data.get('unrealizedPnl', 0))
                        })
            
            # Prepare portfolio data
            portfolio_data = {
                'accountValue': margin_summary.get('accountValue', 0),
                'totalPnl': daily_pnl,
                'openPositions': open_positions,
                'dailyVolume': daily_volume,
                'tradesCount': trades_count
            }
            
            # Send notification
            success = await telegram_service.send_daily_portfolio_summary(user_address, portfolio_data)
            
            if success:
                # Record notification in stats
                stats = await TradingStats.get_or_create(user_address)
                await stats.record_notification()
                
                logger.info(f"✅ Sent daily portfolio summary to {user_address}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error sending portfolio summary to {user_address}: {e}")
            return False
    
    async def send_test_summary(self, user_address: str) -> bool:
        """Send a test portfolio summary (for testing)"""
        return await self._send_user_portfolio_summary(user_address)
    
    def get_statistics(self) -> Dict[str, any]:
        """Get service statistics"""
        return {
            'is_running': self.is_running,
            'notification_hour': self.notification_hour,
            'registered_users_count': len(self.registered_users),
            'last_notifications_count': len(self.last_notification_dates),
            'next_notification_time': self._get_next_notification_time(datetime.utcnow()).isoformat(),
            'api_client_stats': self.api_client.get_statistics() if self.api_client else None
        }

# Global service instance
_daily_portfolio_service: Optional[DailyPortfolioService] = None

def get_daily_portfolio_service() -> Optional[DailyPortfolioService]:
    """Get the global daily portfolio service instance"""
    return _daily_portfolio_service

async def initialize_daily_portfolio_service(hyperliquid_base_url: str, is_testnet: bool = True, notification_hour: int = 9):
    """Initialize the global daily portfolio service"""
    global _daily_portfolio_service
    
    if _daily_portfolio_service:
        logger.warning("Daily portfolio service already initialized")
        return _daily_portfolio_service
    
    try:
        _daily_portfolio_service = DailyPortfolioService(hyperliquid_base_url, is_testnet, notification_hour)
        await _daily_portfolio_service.start()
        
        logger.info("📊 Daily portfolio service initialized")
        return _daily_portfolio_service
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize daily portfolio service: {e}")
        raise

async def cleanup_daily_portfolio_service():
    """Cleanup the global daily portfolio service"""
    global _daily_portfolio_service
    
    if _daily_portfolio_service:
        await _daily_portfolio_service.stop()
        _daily_portfolio_service = None
        logger.info("📊 Daily portfolio service cleaned up")