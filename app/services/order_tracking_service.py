"""
Order Tracking Service Integration
Coordinates WebSocket events with the industry-grade order tracker
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .industry_grade_order_tracker import IndustryGradeOrderTracker, TrackingConfig, TrackingStrategy
from .hyperliquid_api_client import HyperliquidAPIClient
from .order_state_machine import OrderContext, OrderEvent

logger = logging.getLogger(__name__)

class OrderTrackingService:
    """
    Main service that integrates order tracking with the application
    """
    
    def __init__(self, hyperliquid_base_url: str, is_testnet: bool = True):
        self.api_client = HyperliquidAPIClient(hyperliquid_base_url, is_testnet)
        
        # Configure tracking for high reliability
        self.tracking_config = TrackingConfig(
            strategy=TrackingStrategy.HYBRID,
            tracking_duration_seconds=3600,  # Track for 1 hour
            polling_interval_seconds=15,     # Poll every 15 seconds
            websocket_timeout_seconds=45,    # Consider WebSocket dead after 45s
            max_concurrent_orders=500,       # Support up to 500 concurrent orders
            notification_enabled=True
        )
        
        self.tracker = IndustryGradeOrderTracker(self.api_client, self.tracking_config)
        self.is_running = False
        
        # Set up notification callback
        self.tracker.set_notification_callback(self._handle_order_notification)
    
    async def start(self):
        """Start the order tracking service"""
        if self.is_running:
            logger.warning("Order tracking service already running")
            return
        
        try:
            # Start API client
            await self.api_client.start()
            
            # Start tracker
            await self.tracker.start()
            
            self.is_running = True
            logger.info("Order tracking service started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start order tracking service: {e}")
            raise
    
    async def stop(self):
        """Stop the order tracking service"""
        if not self.is_running:
            return
        
        try:
            # Stop tracker
            await self.tracker.stop()
            
            # Stop API client
            await self.api_client.stop()
            
            self.is_running = False
            logger.info("Order tracking service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping order tracking service: {e}")
    
    async def track_order(self, order_id: str, order_context: OrderContext) -> bool:
        """Start tracking a new order"""
        if not self.is_running:
            logger.error("Order tracking service not running")
            return False
        
        return await self.tracker.track_order(order_id, order_context)
    
    async def stop_tracking_order(self, order_id: str, reason: str = "Manual stop") -> bool:
        """Stop tracking a specific order"""
        return await self.tracker.stop_tracking_order(order_id, reason)
    
    async def handle_websocket_event(self, user_address: str, event_data: Dict[str, Any]):
        """Process WebSocket events for order tracking"""
        if not self.is_running:
            return
        
        await self.tracker.handle_websocket_event(user_address, event_data)
    
    async def _handle_order_notification(self, order_id: str, order_context: OrderContext, 
                                       event_type: str, data: Dict[str, Any]):
        """Handle notifications from the order tracker"""
        try:
            # Import here to avoid circular imports
            from app.services.telegram import get_telegram_service
            
            telegram_service = get_telegram_service()
            if not telegram_service:
                logger.debug("Telegram service not available for order notifications")
                return
            
            user_address = order_context.user_address
            
            # Check if user has Telegram notifications enabled
            chat_id = await telegram_service.get_user_chat_id(user_address)
            if not chat_id:
                logger.debug(f"No Telegram chat ID for {user_address} - skipping order notification")
                return
            
            # Send different notifications based on event type
            if event_type == 'order_filled':
                await self._send_order_filled_notification(
                    telegram_service, user_address, order_context, data
                )
            elif event_type == 'order_partially_filled':
                await self._send_partial_fill_notification(
                    telegram_service, user_address, order_context, data
                )
            elif event_type == 'order_cancelled_detected':
                await self._send_order_cancelled_notification(
                    telegram_service, user_address, order_context, data
                )
            elif event_type == 'order_tracking_started':
                await self._send_tracking_started_notification(
                    telegram_service, user_address, order_context, data
                )
            elif event_type in ['order_filled_via_polling', 'order_tracking_completed']:
                # Log but don't send notification to avoid spam
                logger.info(f"Order tracking event {event_type} for {order_id}: {data}")
            
        except Exception as e:
            logger.error(f"Error handling order notification: {e}")
    
    async def _send_order_filled_notification(self, telegram_service, user_address: str, 
                                            order_context: OrderContext, data: Dict[str, Any]):
        """Send order filled notification"""
        try:
            # Get asset name (simplified - you might want to add asset mapping)
            asset_name = f"Asset_{order_context.asset_index}"
            side = "Buy" if order_context.is_buy else "Sell"
            
            fill_price = data.get('fill_price', order_context.price)
            total_filled = data.get('total_filled', order_context.size)
            
            message = f"""✅ **Order Completely Filled!**

🎯 **{asset_name} {side} Order**
• Price: ${fill_price:,.4f}
• Size: {total_filled:.4f}
• Total Value: ${fill_price * total_filled:,.2f}

🔄 **Execution Details**
• Order Type: {order_context.order_type.title()}
• Time in Force: {order_context.time_in_force}

⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"""

            await telegram_service.send_message(
                await telegram_service.get_user_chat_id(user_address), 
                message
            )
            
            logger.info(f"Sent order filled notification for {order_context.order_id}")
            
        except Exception as e:
            logger.error(f"Error sending order filled notification: {e}")
    
    async def _send_partial_fill_notification(self, telegram_service, user_address: str,
                                            order_context: OrderContext, data: Dict[str, Any]):
        """Send partial fill notification"""
        try:
            asset_name = f"Asset_{order_context.asset_index}"
            side = "Buy" if order_context.is_buy else "Sell"
            
            fill_size = data.get('fill_size', 0)
            fill_price = data.get('fill_price', order_context.price)
            total_filled = data.get('total_filled', order_context.filled_size)
            remaining = data.get('remaining', order_context.remaining_size)
            
            fill_percentage = (total_filled / order_context.size) * 100 if order_context.size > 0 else 0
            
            message = f"""📊 **Partial Fill Alert**

🎯 **{asset_name} {side} Order**
• Fill Price: ${fill_price:,.4f}
• Fill Size: {fill_size:.4f}
• Total Filled: {total_filled:.4f} ({fill_percentage:.1f}%)
• Remaining: {remaining:.4f}

⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"""

            await telegram_service.send_message(
                await telegram_service.get_user_chat_id(user_address), 
                message
            )
            
            logger.info(f"Sent partial fill notification for {order_context.order_id}")
            
        except Exception as e:
            logger.error(f"Error sending partial fill notification: {e}")
    
    async def _send_order_cancelled_notification(self, telegram_service, user_address: str,
                                               order_context: OrderContext, data: Dict[str, Any]):
        """Send order cancelled notification"""
        try:
            asset_name = f"Asset_{order_context.asset_index}"
            side = "Buy" if order_context.is_buy else "Sell"
            detection_method = data.get('detection_method', 'unknown')
            
            message = f"""❌ **Order Cancelled**

🎯 **{asset_name} {side} Order**
• Price: ${order_context.price:,.4f}
• Size: {order_context.size:.4f}
• Detection: {detection_method.replace('_', ' ').title()}

⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"""

            await telegram_service.send_message(
                await telegram_service.get_user_chat_id(user_address), 
                message
            )
            
            logger.info(f"Sent order cancelled notification for {order_context.order_id}")
            
        except Exception as e:
            logger.error(f"Error sending order cancelled notification: {e}")
    
    async def _send_tracking_started_notification(self, telegram_service, user_address: str,
                                                order_context: OrderContext, data: Dict[str, Any]):
        """Send tracking started notification (only for debugging)"""
        try:
            if logger.isEnabledFor(logging.DEBUG):
                strategy = data.get('strategy', 'hybrid')
                asset_name = f"Asset_{order_context.asset_index}"
                side = "Buy" if order_context.is_buy else "Sell"
                
                message = f"""🔄 **Order Tracking Started**

🎯 **{asset_name} {side} Order**
• Price: ${order_context.price:,.4f}
• Size: {order_context.size:.4f}
• Strategy: {strategy.title()}

📡 You'll receive updates as the order progresses.

⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"""

                await telegram_service.send_message(
                    await telegram_service.get_user_chat_id(user_address), 
                    message
                )
                
                logger.debug(f"Sent tracking started notification for {order_context.order_id}")
                
        except Exception as e:
            logger.error(f"Error sending tracking started notification: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tracking statistics"""
        if not self.is_running:
            return {'status': 'not_running'}
        
        return {
            'status': 'running',
            'tracker_stats': self.tracker.get_tracking_statistics(),
            'api_client_stats': self.api_client.get_statistics(),
            'config': {
                'strategy': self.tracking_config.strategy.value,
                'tracking_duration': self.tracking_config.tracking_duration_seconds,
                'polling_interval': self.tracking_config.polling_interval_seconds,
                'max_concurrent_orders': self.tracking_config.max_concurrent_orders
            }
        }
    
    def get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a tracked order"""
        if not self.is_running:
            return None
        
        return self.tracker.get_order_details(order_id)
    
    @property
    def state_machine(self):
        """Access to the underlying state machine"""
        return self.tracker.state_machine

# Global service instance
_order_tracking_service: Optional[OrderTrackingService] = None

def get_order_tracking_service() -> Optional[OrderTrackingService]:
    """Get the global order tracking service instance"""
    return _order_tracking_service

async def initialize_order_tracking_service(hyperliquid_base_url: str, is_testnet: bool = True):
    """Initialize the global order tracking service"""
    global _order_tracking_service
    
    if _order_tracking_service:
        logger.warning("Order tracking service already initialized")
        return _order_tracking_service
    
    try:
        _order_tracking_service = OrderTrackingService(hyperliquid_base_url, is_testnet)
        await _order_tracking_service.start()
        
        # Set up integration with signing routes
        from app.routes.signing import set_order_tracking_service
        set_order_tracking_service(_order_tracking_service)
        
        logger.info("Order tracking service initialized and integrated")
        return _order_tracking_service
        
    except Exception as e:
        logger.error(f"Failed to initialize order tracking service: {e}")
        raise

async def cleanup_order_tracking_service():
    """Cleanup the global order tracking service"""
    global _order_tracking_service
    
    if _order_tracking_service:
        await _order_tracking_service.stop()
        _order_tracking_service = None
        logger.info("Order tracking service cleaned up")