"""
Industry-Grade Order Tracker
Combines WebSocket real-time updates with API polling fallback for 100% reliability
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any
import json
from dataclasses import dataclass
from enum import Enum

from .order_state_machine import OrderStateMachine, OrderState, OrderEvent, OrderContext
from .hyperliquid_api_client import HyperliquidAPIClient

logger = logging.getLogger(__name__)

class TrackingStrategy(Enum):
    """Order tracking strategies"""
    WEBSOCKET_ONLY = "websocket_only"
    POLLING_ONLY = "polling_only"
    HYBRID = "hybrid"  # WebSocket + polling fallback

@dataclass
class TrackingConfig:
    """Configuration for order tracking"""
    strategy: TrackingStrategy = TrackingStrategy.HYBRID
    tracking_duration_seconds: int = 3600  # 1 hour default
    polling_interval_seconds: int = 10  # Poll every 10 seconds
    websocket_timeout_seconds: int = 30  # Consider WebSocket dead after 30s
    max_concurrent_orders: int = 1000
    notification_enabled: bool = True

class OrderTracker:
    """Individual order tracker with dual-source monitoring"""
    
    def __init__(self, order_id: str, order_context: OrderContext, config: TrackingConfig,
                 notification_callback: Optional[Callable] = None):
        self.order_id = order_id
        self.order_context = order_context
        self.config = config
        self.notification_callback = notification_callback
        
        # Tracking state
        self.created_at = datetime.utcnow()
        self.last_websocket_update = None
        self.last_api_poll = None
        self.is_active = True
        self.websocket_events_received = 0
        self.api_polls_completed = 0
        
        # Event tracking
        self.recent_events: List[Dict[str, Any]] = []
        self.state_history: List[Dict[str, Any]] = []
    
    def should_continue_tracking(self) -> bool:
        """Check if we should continue tracking this order"""
        if not self.is_active:
            return False
        
        # Stop tracking after configured duration
        age = (datetime.utcnow() - self.created_at).total_seconds()
        if age > self.config.tracking_duration_seconds:
            logger.info(f"Order {self.order_id} tracking expired after {age:.0f}s")
            return False
        
        # Stop tracking if order is in terminal state
        current_state = OrderState(self.order_context.metadata.get('state', OrderState.PENDING.value))
        if current_state in {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, 
                            OrderState.EXPIRED, OrderState.FAILED}:
            logger.info(f"Order {self.order_id} reached terminal state: {current_state.value}")
            return False
        
        return True
    
    def should_use_polling_fallback(self) -> bool:
        """Determine if we should use API polling as fallback"""
        if self.config.strategy == TrackingStrategy.POLLING_ONLY:
            return True
        
        if self.config.strategy == TrackingStrategy.WEBSOCKET_ONLY:
            return False
        
        # For hybrid strategy, use polling if WebSocket seems inactive
        if self.last_websocket_update:
            time_since_ws = (datetime.utcnow() - self.last_websocket_update).total_seconds()
            return time_since_ws > self.config.websocket_timeout_seconds
        
        # Use polling if we haven't received WebSocket updates yet
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.config.websocket_timeout_seconds
    
    def record_websocket_event(self, event_data: Dict[str, Any]):
        """Record WebSocket event reception"""
        self.last_websocket_update = datetime.utcnow()
        self.websocket_events_received += 1
        
        event_record = {
            'timestamp': self.last_websocket_update,
            'source': 'websocket',
            'data': event_data
        }
        self.recent_events.append(event_record)
        
        # Keep only recent events
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        self.recent_events = [e for e in self.recent_events if e['timestamp'] > cutoff]
    
    def record_api_poll(self, poll_result: Dict[str, Any]):
        """Record API polling result"""
        self.last_api_poll = datetime.utcnow()
        self.api_polls_completed += 1
        
        event_record = {
            'timestamp': self.last_api_poll,
            'source': 'api_poll',
            'data': poll_result
        }
        self.recent_events.append(event_record)
        
        # Keep only recent events
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        self.recent_events = [e for e in self.recent_events if e['timestamp'] > cutoff]
    
    def record_state_change(self, old_state: OrderState, new_state: OrderState, trigger_source: str):
        """Record state change for debugging"""
        state_change = {
            'timestamp': datetime.utcnow(),
            'old_state': old_state.value,
            'new_state': new_state.value,
            'trigger_source': trigger_source
        }
        self.state_history.append(state_change)
    
    async def send_notification(self, event_type: str, data: Dict[str, Any]):
        """Send notification if callback is configured"""
        if self.notification_callback and self.config.notification_enabled:
            try:
                await self.notification_callback(self.order_id, self.order_context, event_type, data)
            except Exception as e:
                logger.error(f"Error sending notification for order {self.order_id}: {e}")

class IndustryGradeOrderTracker:
    """
    Professional order tracking system with:
    - WebSocket + API polling hybrid approach
    - Circuit breaker for API reliability
    - Exponential backoff on failures
    - Automatic cleanup and state management
    """
    
    def __init__(self, api_client: HyperliquidAPIClient, config: TrackingConfig = None):
        self.api_client = api_client
        self.config = config or TrackingConfig()
        self.state_machine = OrderStateMachine()
        
        # Active trackers
        self.order_trackers: Dict[str, OrderTracker] = {}
        
        # Background tasks
        self.polling_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Statistics
        self.stats = {
            'orders_tracked': 0,
            'websocket_events_processed': 0,
            'api_polls_completed': 0,
            'notifications_sent': 0,
            'orders_completed': 0
        }
        
        # Notification callback
        self.notification_callback: Optional[Callable] = None
    
    async def start(self):
        """Start the order tracking service"""
        if self.is_running:
            logger.warning("Order tracker already running")
            return
        
        self.is_running = True
        
        # Start background tasks
        self.polling_task = asyncio.create_task(self._polling_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Industry-grade order tracker started with strategy: {self.config.strategy.value}")
    
    async def stop(self):
        """Stop the order tracking service"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel background tasks
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Industry-grade order tracker stopped")
    
    def set_notification_callback(self, callback: Callable):
        """Set notification callback for order events"""
        self.notification_callback = callback
        logger.info("Notification callback configured")
    
    async def track_order(self, order_id: str, order_context: OrderContext) -> bool:
        """Start tracking a new order"""
        try:
            if len(self.order_trackers) >= self.config.max_concurrent_orders:
                logger.error(f"Maximum concurrent orders ({self.config.max_concurrent_orders}) reached")
                return False
            
            if order_id in self.order_trackers:
                logger.warning(f"Order {order_id} already being tracked")
                return False
            
            # Create order in state machine
            if not self.state_machine.create_order(order_id, order_context):
                logger.error(f"Failed to create order {order_id} in state machine")
                return False
            
            # Create tracker
            tracker = OrderTracker(
                order_id=order_id,
                order_context=order_context,
                config=self.config,
                notification_callback=self._handle_notification
            )
            
            self.order_trackers[order_id] = tracker
            self.stats['orders_tracked'] += 1
            
            logger.info(f"Started tracking order {order_id} for user {order_context.user_address}")
            
            # Send initial notification
            await tracker.send_notification('order_tracking_started', {
                'order_id': order_id,
                'user_address': order_context.user_address,
                'strategy': self.config.strategy.value
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting order tracking for {order_id}: {e}")
            return False
    
    async def stop_tracking_order(self, order_id: str, reason: str = "Manual stop") -> bool:
        """Stop tracking a specific order"""
        try:
            tracker = self.order_trackers.get(order_id)
            if not tracker:
                logger.warning(f"Order {order_id} not being tracked")
                return False
            
            tracker.is_active = False
            
            # Send final notification
            await tracker.send_notification('order_tracking_stopped', {
                'order_id': order_id,
                'reason': reason
            })
            
            logger.info(f"Stopped tracking order {order_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping order tracking for {order_id}: {e}")
            return False
    
    async def handle_websocket_event(self, user_address: str, event_data: Dict[str, Any]):
        """Process WebSocket events for order tracking"""
        try:
            # Find relevant orders for this user
            user_orders = [
                (order_id, tracker) for order_id, tracker in self.order_trackers.items()
                if tracker.order_context.user_address.lower() == user_address.lower() and tracker.is_active
            ]
            
            if not user_orders:
                return
            
            # Process different types of WebSocket events
            if 'fills' in event_data:
                await self._process_fill_events(user_orders, event_data['fills'])
            
            if 'userEvents' in event_data:
                await self._process_user_events(user_orders, event_data['userEvents'])
            
            # Record WebSocket activity for all user orders
            for order_id, tracker in user_orders:
                tracker.record_websocket_event(event_data)
            
            self.stats['websocket_events_processed'] += 1
            
        except Exception as e:
            logger.error(f"Error processing WebSocket event for {user_address}: {e}")
    
    async def _process_fill_events(self, user_orders: List[tuple], fills: List[Dict[str, Any]]):
        """Process fill events from WebSocket"""
        for fill in fills:
            # Extract fill information
            order_id = fill.get('oid')
            if not order_id:
                continue
            
            # Find matching tracked order by order_id or by order parameters if no order_id match
            matching_order = None
            for tracked_order_id, tracker in user_orders:
                # First try to match by exchange order ID if available
                if tracker.order_context.exchange_order_id == str(order_id):
                    matching_order = (tracked_order_id, tracker)
                    break
                
                # If no exchange order ID match, try to match by order parameters and timing
                # This handles the case where we're tracking an order but haven't got the exchange ID yet
                if not tracker.order_context.exchange_order_id:
                    # Check if this fill matches our tracked order parameters
                    fill_coin_index = None
                    try:
                        # Get asset index from coin name if possible (this is approximate)
                        if fill.get('coin') == 'ETH':
                            fill_coin_index = 4  # ETH is typically asset 4
                        elif fill.get('coin') == 'BTC':
                            fill_coin_index = 3  # BTC is typically asset 3
                        # Add more coin mappings as needed
                    except:
                        pass
                    
                    # Match by asset index, size, and timing (within last 5 minutes)
                    if (fill_coin_index == tracker.order_context.asset_index and
                        abs(float(fill.get('sz', 0)) - tracker.order_context.size) < 0.001 and
                        (datetime.utcnow() - tracker.order_context.submitted_at).total_seconds() < 300):
                        
                        # Update the tracker with the exchange order ID for future correlation
                        tracker.order_context.exchange_order_id = str(order_id)
                        matching_order = (tracked_order_id, tracker)
                        logger.info(f"Correlated order {tracked_order_id} with exchange order ID {order_id}")
                        break
            
            if not matching_order:
                continue
            
            tracked_order_id, tracker = matching_order
            
            # Process the fill
            fill_size = float(fill.get('sz', 0))
            fill_price = float(fill.get('px', 0))
            
            # Update order context
            tracker.order_context.filled_size += fill_size
            tracker.order_context.remaining_size = tracker.order_context.size - tracker.order_context.filled_size
            
            # Determine event type
            if tracker.order_context.remaining_size <= 0:
                # Complete fill
                await self.state_machine.trigger_event(
                    tracked_order_id, 
                    OrderEvent.COMPLETE_FILL,
                    {'fill_size': fill_size, 'fill_price': fill_price, 'source': 'websocket'}
                )
                await tracker.send_notification('order_filled', {
                    'fill_size': fill_size,
                    'fill_price': fill_price,
                    'total_filled': tracker.order_context.filled_size
                })
            else:
                # Partial fill
                await self.state_machine.trigger_event(
                    tracked_order_id,
                    OrderEvent.PARTIAL_FILL,
                    {'fill_size': fill_size, 'fill_price': fill_price, 'source': 'websocket'}
                )
                await tracker.send_notification('order_partially_filled', {
                    'fill_size': fill_size,
                    'fill_price': fill_price,
                    'total_filled': tracker.order_context.filled_size,
                    'remaining': tracker.order_context.remaining_size
                })
    
    async def _process_user_events(self, user_orders: List[tuple], user_events: List[Dict[str, Any]]):
        """Process user events from WebSocket"""
        for event in user_events:
            event_type = event.get('type')
            
            if event_type == 'order':
                order_data = event.get('data', {})
                order_id = order_data.get('oid')
                
                if not order_id:
                    continue
                
                # Find matching tracked order
                matching_order = None
                for tracked_order_id, tracker in user_orders:
                    if tracker.order_context.exchange_order_id == str(order_id):
                        matching_order = (tracked_order_id, tracker)
                        break
                
                if matching_order:
                    tracked_order_id, tracker = matching_order
                    
                    # Process order status change
                    status = order_data.get('status', 'unknown')
                    
                    if status == 'open':
                        await self.state_machine.trigger_event(
                            tracked_order_id,
                            OrderEvent.CONFIRM_OPEN,
                            {'source': 'websocket', 'order_data': order_data}
                        )
                    elif status == 'cancelled':
                        await self.state_machine.trigger_event(
                            tracked_order_id,
                            OrderEvent.CANCEL,
                            {'source': 'websocket', 'reason': 'Exchange cancelled'}
                        )
                    elif status == 'rejected':
                        await self.state_machine.trigger_event(
                            tracked_order_id,
                            OrderEvent.REJECT,
                            {'source': 'websocket', 'reason': order_data.get('rejectReason', 'Unknown')}
                        )
    
    async def _polling_loop(self):
        """Background polling loop for API fallback"""
        while self.is_running:
            try:
                # Get orders that need polling
                orders_to_poll = [
                    (order_id, tracker) for order_id, tracker in self.order_trackers.items()
                    if tracker.should_continue_tracking() and tracker.should_use_polling_fallback()
                ]
                
                if orders_to_poll:
                    await self._poll_order_statuses(orders_to_poll)
                
                await asyncio.sleep(self.config.polling_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _poll_order_statuses(self, orders_to_poll: List[tuple]):
        """Poll API for order status updates"""
        try:
            # Group orders by user for efficient batch queries
            user_orders: Dict[str, List[tuple]] = {}
            for order_id, tracker in orders_to_poll:
                user_addr = tracker.order_context.user_address.lower()
                if user_addr not in user_orders:
                    user_orders[user_addr] = []
                user_orders[user_addr].append((order_id, tracker))
            
            # Poll each user's orders
            for user_address, user_order_list in user_orders.items():
                await self._poll_user_orders(user_address, user_order_list)
            
        except Exception as e:
            logger.error(f"Error polling order statuses: {e}")
    
    async def _poll_user_orders(self, user_address: str, user_order_list: List[tuple]):
        """Poll orders for a specific user"""
        try:
            # Get exchange order IDs for batch query
            exchange_order_ids = []
            order_mapping = {}
            
            for order_id, tracker in user_order_list:
                if tracker.order_context.exchange_order_id:
                    exchange_id = int(tracker.order_context.exchange_order_id)
                    exchange_order_ids.append(exchange_id)
                    order_mapping[exchange_id] = (order_id, tracker)
            
            if not exchange_order_ids:
                return
            
            # Batch query order statuses
            order_statuses = await self.api_client.batch_get_order_statuses(user_address, exchange_order_ids)
            
            # Process results
            for exchange_id, order_status in order_statuses.items():
                if exchange_id not in order_mapping:
                    continue
                
                order_id, tracker = order_mapping[exchange_id]
                tracker.record_api_poll({'status': order_status})
                
                if order_status is None:
                    # Order not found in open orders - likely filled or cancelled
                    await self._handle_missing_order(order_id, tracker, user_address)
                else:
                    # Order still open - update state if needed
                    await self._handle_open_order_update(order_id, tracker, order_status)
            
            self.stats['api_polls_completed'] += 1
            
        except Exception as e:
            logger.error(f"Error polling orders for user {user_address}: {e}")
    
    async def _handle_missing_order(self, order_id: str, tracker: OrderTracker, user_address: str):
        """Handle case where order is missing from open orders (likely filled/cancelled)"""
        try:
            # Query recent fills to determine what happened
            fills_success, recent_fills = await self.api_client.get_user_fills(
                user_address, 
                start_time=tracker.created_at
            )
            
            if fills_success:
                # Look for fills matching this order
                matching_fills = [
                    fill for fill in recent_fills
                    if fill.get('oid') == int(tracker.order_context.exchange_order_id or 0)
                ]
                
                if matching_fills:
                    # Order was filled
                    total_filled = sum(float(fill.get('sz', 0)) for fill in matching_fills)
                    avg_price = sum(float(fill.get('px', 0)) * float(fill.get('sz', 0)) for fill in matching_fills) / total_filled if total_filled > 0 else 0
                    
                    await self.state_machine.trigger_event(
                        order_id,
                        OrderEvent.COMPLETE_FILL,
                        {'fill_size': total_filled, 'fill_price': avg_price, 'source': 'api_poll'}
                    )
                    
                    await tracker.send_notification('order_filled_via_polling', {
                        'total_filled': total_filled,
                        'average_price': avg_price
                    })
                else:
                    # Order was likely cancelled
                    await self.state_machine.trigger_event(
                        order_id,
                        OrderEvent.CANCEL,
                        {'source': 'api_poll', 'reason': 'Not found in open orders'}
                    )
                    
                    await tracker.send_notification('order_cancelled_detected', {
                        'detection_method': 'api_polling'
                    })
            
        except Exception as e:
            logger.error(f"Error handling missing order {order_id}: {e}")
    
    async def _handle_open_order_update(self, order_id: str, tracker: OrderTracker, order_status: Dict[str, Any]):
        """Handle update for an order that's still open"""
        try:
            # Extract current order information
            order_data = order_status.get('order', {})
            
            # Check if there have been any fills since last update
            # This is a simplified check - in practice you'd want more sophisticated tracking
            
            # Ensure order is marked as open if it's the first time we see it
            current_state = self.state_machine.get_order_state(order_id)
            if current_state in {OrderState.PENDING, OrderState.SUBMITTED}:
                await self.state_machine.trigger_event(
                    order_id,
                    OrderEvent.CONFIRM_OPEN,
                    {'source': 'api_poll', 'order_data': order_data}
                )
            
        except Exception as e:
            logger.error(f"Error handling open order update for {order_id}: {e}")
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.is_running:
            try:
                await self._cleanup_inactive_orders()
                await asyncio.sleep(60)  # Cleanup every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_inactive_orders(self):
        """Clean up orders that no longer need tracking"""
        try:
            orders_to_remove = []
            
            for order_id, tracker in self.order_trackers.items():
                if not tracker.should_continue_tracking():
                    orders_to_remove.append(order_id)
            
            for order_id in orders_to_remove:
                tracker = self.order_trackers[order_id]
                
                # Send final notification
                await tracker.send_notification('order_tracking_completed', {
                    'order_id': order_id,
                    'final_state': self.state_machine.get_order_state(order_id).value if self.state_machine.get_order_state(order_id) else 'unknown',
                    'websocket_events': tracker.websocket_events_received,
                    'api_polls': tracker.api_polls_completed
                })
                
                del self.order_trackers[order_id]
                self.stats['orders_completed'] += 1
            
            if orders_to_remove:
                logger.info(f"Cleaned up {len(orders_to_remove)} completed order trackers")
            
            # Clean up state machine
            self.state_machine.cleanup_old_orders(max_age_hours=1)
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
    
    async def _handle_notification(self, order_id: str, order_context: OrderContext, event_type: str, data: Dict[str, Any]):
        """Handle notifications from order trackers"""
        try:
            if self.notification_callback:
                await self.notification_callback(order_id, order_context, event_type, data)
            
            self.stats['notifications_sent'] += 1
            
        except Exception as e:
            logger.error(f"Error handling notification for order {order_id}: {e}")
    
    def get_tracking_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tracking statistics"""
        active_orders = len([t for t in self.order_trackers.values() if t.is_active])
        
        return {
            **self.stats,
            'active_orders': active_orders,
            'total_orders_in_memory': len(self.order_trackers),
            'state_machine_stats': self.state_machine.get_statistics(),
            'api_client_stats': self.api_client.get_statistics(),
            'config': {
                'strategy': self.config.strategy.value,
                'polling_interval': self.config.polling_interval_seconds,
                'tracking_duration': self.config.tracking_duration_seconds
            }
        }
    
    def get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a tracked order"""
        tracker = self.order_trackers.get(order_id)
        if not tracker:
            return None
        
        current_state = self.state_machine.get_order_state(order_id)
        
        return {
            'order_id': order_id,
            'current_state': current_state.value if current_state else 'unknown',
            'user_address': tracker.order_context.user_address,
            'created_at': tracker.created_at.isoformat(),
            'is_active': tracker.is_active,
            'last_websocket_update': tracker.last_websocket_update.isoformat() if tracker.last_websocket_update else None,
            'last_api_poll': tracker.last_api_poll.isoformat() if tracker.last_api_poll else None,
            'websocket_events_received': tracker.websocket_events_received,
            'api_polls_completed': tracker.api_polls_completed,
            'should_use_polling': tracker.should_use_polling_fallback(),
            'order_context': {
                'asset_index': tracker.order_context.asset_index,
                'is_buy': tracker.order_context.is_buy,
                'price': tracker.order_context.price,
                'size': tracker.order_context.size,
                'filled_size': tracker.order_context.filled_size,
                'remaining_size': tracker.order_context.remaining_size
            },
            'state_history': tracker.state_history,
            'recent_events': [
                {
                    'timestamp': event['timestamp'].isoformat(),
                    'source': event['source'],
                    'data': event['data']
                } for event in tracker.recent_events[-10:]  # Last 10 events
            ]
        }