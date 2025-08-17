"""
Industry-grade Order State Machine
Manages order lifecycle with proper state transitions and validation
"""
import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Set, Callable, Any
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)

class OrderState(Enum):
    """Order states following Hyperliquid order lifecycle"""
    PENDING = "pending"          # Order created but not yet submitted
    SUBMITTED = "submitted"      # Order submitted to exchange
    OPEN = "open"               # Order is open on the exchange
    FILLED = "filled"           # Order completely filled
    PARTIALLY_FILLED = "partially_filled"  # Order partially filled
    CANCELLED = "cancelled"     # Order cancelled
    REJECTED = "rejected"       # Order rejected by exchange
    EXPIRED = "expired"         # Order expired
    FAILED = "failed"           # Order failed (technical error)

class OrderEvent(Enum):
    """Events that trigger state transitions"""
    SUBMIT = "submit"
    CONFIRM_OPEN = "confirm_open"
    PARTIAL_FILL = "partial_fill"
    COMPLETE_FILL = "complete_fill"
    CANCEL = "cancel"
    REJECT = "reject"
    EXPIRE = "expire"
    FAIL = "fail"

@dataclass
class OrderContext:
    """Order context with all relevant data"""
    order_id: Optional[str] = None
    user_address: str = ""
    asset_index: int = 0
    is_buy: bool = True
    price: float = 0.0
    size: float = 0.0
    filled_size: float = 0.0
    remaining_size: float = 0.0
    order_type: str = "limit"
    time_in_force: str = "Ioc"
    
    # Tracking data
    submitted_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    exchange_order_id: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.remaining_size = self.size - self.filled_size

class OrderStateMachine:
    """
    Finite State Machine for order lifecycle management
    Based on industry best practices for reliable order tracking
    """
    
    def __init__(self):
        self.orders: Dict[str, OrderContext] = {}
        self.state_transitions: Dict[OrderState, Dict[OrderEvent, OrderState]] = {}
        self.state_handlers: Dict[OrderState, Callable] = {}
        self.event_handlers: Dict[OrderEvent, Callable] = {}
        self._setup_state_machine()
        
    def _setup_state_machine(self):
        """Initialize state transitions following Hyperliquid order flow"""
        
        # Define valid state transitions
        self.state_transitions = {
            OrderState.PENDING: {
                OrderEvent.SUBMIT: OrderState.SUBMITTED,
                OrderEvent.FAIL: OrderState.FAILED
            },
            OrderState.SUBMITTED: {
                OrderEvent.CONFIRM_OPEN: OrderState.OPEN,
                OrderEvent.REJECT: OrderState.REJECTED,
                OrderEvent.FAIL: OrderState.FAILED,
                OrderEvent.COMPLETE_FILL: OrderState.FILLED  # Immediate fill
            },
            OrderState.OPEN: {
                OrderEvent.PARTIAL_FILL: OrderState.PARTIALLY_FILLED,
                OrderEvent.COMPLETE_FILL: OrderState.FILLED,
                OrderEvent.CANCEL: OrderState.CANCELLED,
                OrderEvent.EXPIRE: OrderState.EXPIRED,
                OrderEvent.REJECT: OrderState.REJECTED
            },
            OrderState.PARTIALLY_FILLED: {
                OrderEvent.PARTIAL_FILL: OrderState.PARTIALLY_FILLED,  # More partial fills
                OrderEvent.COMPLETE_FILL: OrderState.FILLED,
                OrderEvent.CANCEL: OrderState.CANCELLED,
                OrderEvent.EXPIRE: OrderState.EXPIRED
            },
            # Terminal states (no transitions out)
            OrderState.FILLED: {},
            OrderState.CANCELLED: {},
            OrderState.REJECTED: {},
            OrderState.EXPIRED: {},
            OrderState.FAILED: {}
        }
        
        # Set up state handlers
        self.state_handlers = {
            OrderState.PENDING: self._handle_pending_state,
            OrderState.SUBMITTED: self._handle_submitted_state,
            OrderState.OPEN: self._handle_open_state,
            OrderState.PARTIALLY_FILLED: self._handle_partially_filled_state,
            OrderState.FILLED: self._handle_filled_state,
            OrderState.CANCELLED: self._handle_cancelled_state,
            OrderState.REJECTED: self._handle_rejected_state,
            OrderState.EXPIRED: self._handle_expired_state,
            OrderState.FAILED: self._handle_failed_state
        }
        
        # Set up event handlers
        self.event_handlers = {
            OrderEvent.SUBMIT: self._handle_submit_event,
            OrderEvent.CONFIRM_OPEN: self._handle_confirm_open_event,
            OrderEvent.PARTIAL_FILL: self._handle_partial_fill_event,
            OrderEvent.COMPLETE_FILL: self._handle_complete_fill_event,
            OrderEvent.CANCEL: self._handle_cancel_event,
            OrderEvent.REJECT: self._handle_reject_event,
            OrderEvent.EXPIRE: self._handle_expire_event,
            OrderEvent.FAIL: self._handle_fail_event
        }
    
    def create_order(self, order_id: str, order_context: OrderContext) -> bool:
        """Create a new order in PENDING state"""
        try:
            if order_id in self.orders:
                logger.warning(f"Order {order_id} already exists")
                return False
                
            order_context.last_updated = datetime.utcnow()
            self.orders[order_id] = order_context
            
            logger.info(f"Created order {order_id} in PENDING state")
            return True
            
        except Exception as e:
            logger.error(f"Error creating order {order_id}: {e}")
            return False
    
    def get_order_state(self, order_id: str) -> Optional[OrderState]:
        """Get current state of an order"""
        order = self.orders.get(order_id)
        if not order:
            return None
        return OrderState(order.metadata.get('state', OrderState.PENDING.value))
    
    def get_order_context(self, order_id: str) -> Optional[OrderContext]:
        """Get order context"""
        return self.orders.get(order_id)
    
    def get_orders_by_state(self, state: OrderState) -> Dict[str, OrderContext]:
        """Get all orders in a specific state"""
        return {
            order_id: context for order_id, context in self.orders.items()
            if context.metadata.get('state') == state.value
        }
    
    def get_orders_by_user(self, user_address: str) -> Dict[str, OrderContext]:
        """Get all orders for a specific user"""
        return {
            order_id: context for order_id, context in self.orders.items()
            if context.user_address.lower() == user_address.lower()
        }
    
    async def trigger_event(self, order_id: str, event: OrderEvent, event_data: Dict[str, Any] = None) -> bool:
        """Trigger an event for an order"""
        try:
            order = self.orders.get(order_id)
            if not order:
                logger.error(f"Order {order_id} not found")
                return False
            
            current_state = OrderState(order.metadata.get('state', OrderState.PENDING.value))
            
            # Check if transition is valid
            valid_events = self.state_transitions.get(current_state, {})
            if event not in valid_events:
                logger.warning(f"Invalid event {event.value} for order {order_id} in state {current_state.value}")
                return False
            
            new_state = valid_events[event]
            
            # Update order context with event data
            if event_data:
                order.metadata.update(event_data)
            
            # Execute event handler
            if event in self.event_handlers:
                await self.event_handlers[event](order_id, order, event_data or {})
            
            # Transition to new state
            old_state = current_state
            order.metadata['state'] = new_state.value
            order.metadata['previous_state'] = old_state.value
            order.last_updated = datetime.utcnow()
            
            logger.info(f"Order {order_id} transitioned from {old_state.value} to {new_state.value}")
            
            # Execute state handler
            if new_state in self.state_handlers:
                await self.state_handlers[new_state](order_id, order)
            
            return True
            
        except Exception as e:
            logger.error(f"Error triggering event {event.value} for order {order_id}: {e}")
            return False
    
    def is_terminal_state(self, state: OrderState) -> bool:
        """Check if state is terminal (no further transitions)"""
        return state in {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, 
                        OrderState.EXPIRED, OrderState.FAILED}
    
    def cleanup_old_orders(self, max_age_hours: int = 24) -> int:
        """Clean up old orders in terminal states"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        orders_to_remove = []
        for order_id, order in self.orders.items():
            if (order.last_updated and order.last_updated < cutoff_time and 
                self.is_terminal_state(OrderState(order.metadata.get('state', OrderState.PENDING.value)))):
                orders_to_remove.append(order_id)
        
        for order_id in orders_to_remove:
            del self.orders[order_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old orders")
        
        return cleaned_count
    
    # State handlers
    async def _handle_pending_state(self, order_id: str, order: OrderContext):
        """Handle order in PENDING state"""
        logger.debug(f"Order {order_id} is pending submission")
    
    async def _handle_submitted_state(self, order_id: str, order: OrderContext):
        """Handle order in SUBMITTED state"""
        order.submitted_at = datetime.utcnow()
        logger.info(f"Order {order_id} submitted to exchange")
    
    async def _handle_open_state(self, order_id: str, order: OrderContext):
        """Handle order in OPEN state"""
        logger.info(f"Order {order_id} is open on exchange")
    
    async def _handle_partially_filled_state(self, order_id: str, order: OrderContext):
        """Handle order in PARTIALLY_FILLED state"""
        fill_percentage = (order.filled_size / order.size) * 100 if order.size > 0 else 0
        logger.info(f"Order {order_id} partially filled: {fill_percentage:.1f}%")
    
    async def _handle_filled_state(self, order_id: str, order: OrderContext):
        """Handle order in FILLED state"""
        logger.info(f"Order {order_id} completely filled")
    
    async def _handle_cancelled_state(self, order_id: str, order: OrderContext):
        """Handle order in CANCELLED state"""
        logger.info(f"Order {order_id} cancelled")
    
    async def _handle_rejected_state(self, order_id: str, order: OrderContext):
        """Handle order in REJECTED state"""
        reason = order.metadata.get('rejection_reason', 'Unknown')
        logger.warning(f"Order {order_id} rejected: {reason}")
    
    async def _handle_expired_state(self, order_id: str, order: OrderContext):
        """Handle order in EXPIRED state"""
        logger.info(f"Order {order_id} expired")
    
    async def _handle_failed_state(self, order_id: str, order: OrderContext):
        """Handle order in FAILED state"""
        error = order.metadata.get('error', 'Unknown error')
        logger.error(f"Order {order_id} failed: {error}")
    
    # Event handlers
    async def _handle_submit_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle order submission"""
        exchange_order_id = event_data.get('exchange_order_id')
        if exchange_order_id:
            order.exchange_order_id = exchange_order_id
        logger.info(f"Submitting order {order_id} to exchange")
    
    async def _handle_confirm_open_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle order confirmation as open"""
        logger.info(f"Order {order_id} confirmed open on exchange")
    
    async def _handle_partial_fill_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle partial fill"""
        fill_size = event_data.get('fill_size', 0)
        fill_price = event_data.get('fill_price', 0)
        
        order.filled_size = min(order.filled_size + fill_size, order.size)
        order.remaining_size = order.size - order.filled_size
        
        logger.info(f"Order {order_id} partial fill: {fill_size} @ {fill_price}")
    
    async def _handle_complete_fill_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle complete fill"""
        fill_price = event_data.get('fill_price', 0)
        order.filled_size = order.size
        order.remaining_size = 0
        
        logger.info(f"Order {order_id} completely filled @ {fill_price}")
    
    async def _handle_cancel_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle order cancellation"""
        reason = event_data.get('reason', 'User requested')
        order.metadata['cancellation_reason'] = reason
        logger.info(f"Order {order_id} cancelled: {reason}")
    
    async def _handle_reject_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle order rejection"""
        reason = event_data.get('reason', 'Unknown rejection reason')
        order.metadata['rejection_reason'] = reason
        logger.warning(f"Order {order_id} rejected: {reason}")
    
    async def _handle_expire_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle order expiration"""
        logger.info(f"Order {order_id} expired")
    
    async def _handle_fail_event(self, order_id: str, order: OrderContext, event_data: Dict[str, Any]):
        """Handle order failure"""
        error = event_data.get('error', 'Unknown error')
        order.metadata['error'] = error
        logger.error(f"Order {order_id} failed: {error}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get order statistics"""
        stats = {
            'total_orders': len(self.orders),
            'by_state': {},
            'active_orders': 0,
            'terminal_orders': 0
        }
        
        for order in self.orders.values():
            state = OrderState(order.metadata.get('state', OrderState.PENDING.value))
            stats['by_state'][state.value] = stats['by_state'].get(state.value, 0) + 1
            
            if self.is_terminal_state(state):
                stats['terminal_orders'] += 1
            else:
                stats['active_orders'] += 1
        
        return stats