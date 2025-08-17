"""
Fill Notification Service for HyperSwipe
API-based reliable fill tracking and Telegram notifications
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from app.services.hyperliquid_api_client import HyperliquidAPIClient
from app.models.database import TelegramUser, NotificationSettings, TradingStats

logger = logging.getLogger(__name__)

class FillNotificationService:
    """
    Reliable API-based fill notification service
    Polls Hyperliquid API for fills and sends Telegram notifications
    """
    
    def __init__(self, hyperliquid_base_url: str, is_testnet: bool = True, poll_interval: int = 12):
        self.api_client = HyperliquidAPIClient(hyperliquid_base_url, is_testnet)
        self.poll_interval = poll_interval  # seconds
        self.is_running = False
        self.polling_task: Optional[asyncio.Task] = None
        
        # Track service start time to avoid historical notification spam
        self.service_start_time = datetime.utcnow()
        
        # Track last seen fill timestamp per user to avoid duplicates
        self.last_fill_timestamps: Dict[str, int] = {}
        
        # Track registered users to optimize polling
        self.registered_users: Set[str] = set()
        self.last_user_refresh = datetime.utcnow()
        self.user_refresh_interval = 60  # seconds
        
    async def start(self):
        """Start the fill notification service"""
        if self.is_running:
            logger.warning("Fill notification service already running")
            return
        
        try:
            # Start API client
            await self.api_client.start()
            
            # Refresh registered users and initialize timestamps to prevent spam
            await self._refresh_registered_users()
            await self._initialize_user_timestamps()
            
            # Start polling task
            self.polling_task = asyncio.create_task(self._polling_loop())
            self.is_running = True
            
            logger.info(f"🔔 Fill notification service started (poll interval: {self.poll_interval}s)")
            
        except Exception as e:
            logger.error(f"❌ Failed to start fill notification service: {e}")
            raise
    
    async def stop(self):
        """Stop the fill notification service"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.polling_task and not self.polling_task.done():
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        
        await self.api_client.stop()
        logger.info("🔔 Fill notification service stopped")
    
    async def _refresh_registered_users(self):
        """Refresh list of users with Telegram notifications enabled"""
        try:
            # Get all active Telegram users
            telegram_users = await TelegramUser.find({"is_active": True}).to_list()
            
            new_registered_users = set()
            for user in telegram_users:
                # Check if fill notifications are enabled
                settings = await NotificationSettings.get_or_create(user.wallet_address)
                if settings.fill_notifications:
                    new_registered_users.add(user.wallet_address.lower())
            
            # Log changes
            added_users = new_registered_users - self.registered_users
            removed_users = self.registered_users - new_registered_users
            
            if added_users:
                logger.info(f"➕ Added {len(added_users)} users for fill tracking: {list(added_users)[:3]}...")
            if removed_users:
                logger.info(f"➖ Removed {len(removed_users)} users from fill tracking: {list(removed_users)[:3]}...")
            
            self.registered_users = new_registered_users
            self.last_user_refresh = datetime.utcnow()
            
            logger.debug(f"📋 Tracking fills for {len(self.registered_users)} registered users")
            
        except Exception as e:
            logger.error(f"❌ Error refreshing registered users: {e}")
    
    async def _initialize_user_timestamps(self):
        """Initialize user timestamps to service start time to prevent historical spam"""
        try:
            service_start_timestamp = int(self.service_start_time.timestamp() * 1000)
            
            for user_address in self.registered_users:
                if user_address not in self.last_fill_timestamps:
                    # Set to service start time to only track new fills from now on
                    self.last_fill_timestamps[user_address] = service_start_timestamp
                    logger.debug(f"🕒 Initialized timestamp for {user_address} to service start time")
            
            logger.info(f"⏰ Initialized {len(self.registered_users)} users to track fills from service start time only")
            
        except Exception as e:
            logger.error(f"❌ Error initializing user timestamps: {e}")
    
    async def _polling_loop(self):
        """Main polling loop for fill notifications"""
        logger.info("🔄 Starting fill notification polling loop")
        
        while self.is_running:
            try:
                # Refresh registered users periodically
                if (datetime.utcnow() - self.last_user_refresh).total_seconds() > self.user_refresh_interval:
                    await self._refresh_registered_users()
                
                # Skip if no registered users
                if not self.registered_users:
                    logger.debug("👥 No registered users for fill tracking - skipping poll")
                    await asyncio.sleep(self.poll_interval)
                    continue
                
                # Process fills for all registered users
                await self._process_all_user_fills()
                
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in polling loop: {e}")
                # Continue polling even on errors
                await asyncio.sleep(self.poll_interval)
    
    async def _process_all_user_fills(self):
        """Process fills for all registered users"""
        start_time = datetime.utcnow()
        
        # Process users in batches to avoid overwhelming the API
        user_list = list(self.registered_users)
        batch_size = 5
        
        for i in range(0, len(user_list), batch_size):
            batch = user_list[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self._process_user_fills(user_address) for user_address in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Small delay between batches to be nice to the API
            if i + batch_size < len(user_list):
                await asyncio.sleep(0.5)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        logger.debug(f"⏱️ Processed fills for {len(user_list)} users in {processing_time:.2f}s")
    
    async def _process_user_fills(self, user_address: str):
        """Process fills for a specific user"""
        try:
            # Get last seen timestamp for this user
            last_timestamp = self.last_fill_timestamps.get(user_address, 0)
            
            # Look for fills in the last 5 minutes (or since last seen)
            start_time = datetime.utcnow() - timedelta(minutes=5)
            if last_timestamp > 0:
                # Use last seen timestamp if it's more recent
                last_seen_time = datetime.fromtimestamp(last_timestamp / 1000)
                if last_seen_time > start_time:
                    start_time = last_seen_time
            
            # Get fills from API
            success, fills = await self.api_client.get_user_fills(user_address, start_time)
            
            if not success:
                logger.warning(f"⚠️ Failed to get fills for {user_address}")
                return
            
            if not fills:
                logger.debug(f"📊 No new fills for {user_address}")
                return
            
            # Filter out fills we've already processed
            new_fills = []
            latest_timestamp = last_timestamp
            
            for fill in fills:
                fill_time = fill.get('time', 0)
                if fill_time > last_timestamp:
                    new_fills.append(fill)
                    latest_timestamp = max(latest_timestamp, fill_time)
            
            if not new_fills:
                logger.debug(f"📊 No new fills since last check for {user_address}")
                return
            
            # Update last seen timestamp
            self.last_fill_timestamps[user_address] = latest_timestamp
            
            # Sort fills by time (oldest first)
            new_fills.sort(key=lambda x: x.get('time', 0))
            
            logger.info(f"🆕 Found {len(new_fills)} new fills for {user_address}")
            
            # Send notifications for each new fill
            for fill in new_fills:
                await self._send_fill_notification(user_address, fill)
            
        except Exception as e:
            logger.error(f"❌ Error processing fills for {user_address}: {e}")
    
    async def _send_fill_notification(self, user_address: str, fill: dict):
        """Send Telegram notification for a single fill"""
        try:
            from app.services.telegram import get_telegram_service
            
            telegram_service = get_telegram_service()
            if not telegram_service:
                logger.warning("⚠️ Telegram service not available")
                return
            
            # Check if user has Telegram notifications enabled
            chat_id = await telegram_service.get_user_chat_id(user_address)
            if not chat_id:
                logger.debug(f"🔍 No Telegram chat ID for {user_address}")
                return
            
            # Get notification settings
            settings = await NotificationSettings.get_or_create(user_address)
            if not settings.fill_notifications:
                logger.debug(f"🔕 Fill notifications disabled for {user_address}")
                return
            
            # Extract fill data
            coin = fill.get('coin', 'Unknown')
            side = fill.get('side', 'Unknown')  # 'B' for buy, 'A' for sell
            px = float(fill.get('px', 0))
            sz = float(fill.get('sz', 0))
            fee = float(fill.get('fee', 0))
            fill_time = fill.get('time', 0)
            direction = fill.get('dir', 'Unknown')  # 'Open Long', 'Close Short', etc.
            
            # Calculate trade volume
            trade_volume = px * sz
            
            # Check minimum notification amount
            if trade_volume < settings.min_notification_amount:
                logger.debug(f"🔕 Fill volume ${trade_volume:.2f} below threshold ${settings.min_notification_amount}")
                return
            
            # Convert Hyperliquid side format to Telegram format
            # 'B' = Buy/Bid, 'A' = Ask/Sell -> 'B' = Buy, 'S' = Sell
            telegram_side = 'B' if side == 'B' else 'S'
            
            # Create fill notification data
            fill_data = {
                'coin': coin,
                'side': telegram_side,
                'px': str(px),
                'sz': str(sz),
                'fee': str(fee),
                'direction': direction,
                'volume': str(trade_volume)
            }
            
            # Send notification
            success = await telegram_service.send_position_fill_alert(user_address, fill_data)
            
            if success:
                # Record notification in stats
                stats = await TradingStats.get_or_create(user_address)
                await stats.record_notification()
                await stats.record_trade(volume=trade_volume, pnl=0.0)
                
                logger.info(f"✅ Sent fill notification: {user_address} {coin} {direction} {sz}@${px}")
            else:
                logger.warning(f"⚠️ Failed to send fill notification for {user_address}")
                
        except Exception as e:
            logger.error(f"❌ Error sending fill notification: {e}")
    
    def get_statistics(self) -> Dict[str, any]:
        """Get service statistics"""
        return {
            'is_running': self.is_running,
            'registered_users_count': len(self.registered_users),
            'tracked_users': len(self.last_fill_timestamps),
            'last_user_refresh': self.last_user_refresh.isoformat(),
            'poll_interval': self.poll_interval,
            'api_client_stats': self.api_client.get_statistics() if self.api_client else None
        }

# Global service instance
_fill_notification_service: Optional[FillNotificationService] = None

def get_fill_notification_service() -> Optional[FillNotificationService]:
    """Get the global fill notification service instance"""
    return _fill_notification_service

async def initialize_fill_notification_service(hyperliquid_base_url: str, is_testnet: bool = True):
    """Initialize the global fill notification service"""
    global _fill_notification_service
    
    if _fill_notification_service:
        logger.warning("Fill notification service already initialized")
        return _fill_notification_service
    
    try:
        _fill_notification_service = FillNotificationService(hyperliquid_base_url, is_testnet)
        await _fill_notification_service.start()
        
        logger.info("🔔 Fill notification service initialized")
        return _fill_notification_service
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize fill notification service: {e}")
        raise

async def cleanup_fill_notification_service():
    """Cleanup the global fill notification service"""
    global _fill_notification_service
    
    if _fill_notification_service:
        await _fill_notification_service.stop()
        _fill_notification_service = None
        logger.info("🔔 Fill notification service cleaned up")