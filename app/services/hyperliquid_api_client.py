"""
Hyperliquid API Client for Order Status Queries
Industry-grade API client with proper error handling and retry logic
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import aiohttp
import json
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class APIEndpoint(Enum):
    """Hyperliquid API endpoints"""
    USER_STATE = "/info"
    ORDER_STATUS = "/info"
    OPEN_ORDERS = "/info"
    USER_FILLS = "/info"

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker for API reliability"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        """Check if we can execute a request"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if (datetime.utcnow() - self.last_failure_time).total_seconds() > self.config.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls
        return False
    
    def on_success(self):
        """Handle successful request"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
    
    def on_failure(self):
        """Handle failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN

class HyperliquidAPIClient:
    """
    Professional Hyperliquid API client with:
    - Circuit breaker pattern
    - Exponential backoff retry
    - Rate limiting
    - Error categorization
    """
    
    def __init__(self, base_url: str, is_testnet: bool = True):
        self.base_url = base_url.rstrip('/')
        self.is_testnet = is_testnet
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        
        # Rate limiting
        self.request_timestamps: List[datetime] = []
        self.max_requests_per_second = 10
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0  # seconds
        self.max_delay = 30.0  # seconds
    
    async def start(self):
        """Initialize the API client"""
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )
        logger.info(f"Hyperliquid API client started (testnet={self.is_testnet})")
    
    async def stop(self):
        """Cleanup the API client"""
        if self.session:
            await self.session.close()
        logger.info("Hyperliquid API client stopped")
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        now = datetime.utcnow()
        
        # Clean old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if (now - ts).total_seconds() < 1.0
        ]
        
        # Check if we need to wait
        if len(self.request_timestamps) >= self.max_requests_per_second:
            sleep_time = 1.0 - (now - self.request_timestamps[0]).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.request_timestamps.append(now)
    
    async def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Tuple[bool, Dict[str, Any]]:
        """Make HTTP request with circuit breaker and retry logic"""
        if not self.circuit_breaker.can_execute():
            logger.warning("Circuit breaker is OPEN - request blocked")
            return False, {"error": "Circuit breaker is open"}
        
        if not self.session:
            await self.start()
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries + 1):
            try:
                await self._rate_limit()
                
                if method.upper() == "POST":
                    async with self.session.post(url, json=data) as response:
                        response_data = await response.json()
                        
                        if response.status == 200:
                            self.circuit_breaker.on_success()
                            return True, response_data
                        else:
                            logger.warning(f"API request failed with status {response.status}: {response_data}")
                            
                            # Don't retry for client errors (4xx)
                            if 400 <= response.status < 500:
                                self.circuit_breaker.on_failure()
                                return False, response_data
                            
                            # Retry for server errors (5xx)
                            if attempt < self.max_retries:
                                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                                logger.info(f"Retrying request in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                                await asyncio.sleep(delay)
                                continue
                            
                            self.circuit_breaker.on_failure()
                            return False, response_data
                
                else:  # GET request
                    async with self.session.get(url, params=data) as response:
                        response_data = await response.json()
                        
                        if response.status == 200:
                            self.circuit_breaker.on_success()
                            return True, response_data
                        else:
                            logger.warning(f"API request failed with status {response.status}: {response_data}")
                            
                            if 400 <= response.status < 500:
                                self.circuit_breaker.on_failure()
                                return False, response_data
                            
                            if attempt < self.max_retries:
                                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                                logger.info(f"Retrying request in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                                await asyncio.sleep(delay)
                                continue
                            
                            self.circuit_breaker.on_failure()
                            return False, response_data
                            
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
                    continue
                self.circuit_breaker.on_failure()
                return False, {"error": "Request timeout"}
                
            except Exception as e:
                logger.error(f"Request error (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
                    continue
                self.circuit_breaker.on_failure()
                return False, {"error": str(e)}
        
        return False, {"error": "Max retries exceeded"}
    
    async def get_user_state(self, user_address: str) -> Tuple[bool, Dict[str, Any]]:
        """Get complete user state including positions and orders"""
        data = {
            "type": "clearinghouseState",
            "user": user_address
        }
        
        success, response = await self._make_request("POST", "/info", data)
        
        if success:
            logger.debug(f"Retrieved user state for {user_address}")
        else:
            logger.error(f"Failed to get user state for {user_address}: {response}")
        
        return success, response
    
    async def get_open_orders(self, user_address: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """Get open orders for a user"""
        data = {
            "type": "openOrders",
            "user": user_address
        }
        
        success, response = await self._make_request("POST", "/info", data)
        
        if success:
            open_orders = response if isinstance(response, list) else []
            logger.debug(f"Retrieved {len(open_orders)} open orders for {user_address}")
            return True, open_orders
        else:
            logger.error(f"Failed to get open orders for {user_address}: {response}")
            return False, []
    
    async def get_order_status(self, user_address: str, order_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Get status of a specific order"""
        # First get all open orders
        success, open_orders = await self.get_open_orders(user_address)
        
        if not success:
            return False, None
        
        # Find the specific order
        for order in open_orders:
            if order.get('order', {}).get('oid') == order_id:
                logger.debug(f"Found order {order_id} for {user_address}")
                return True, order
        
        # Order not found in open orders - might be filled/cancelled
        logger.debug(f"Order {order_id} not found in open orders for {user_address}")
        return True, None
    
    async def get_user_fills(self, user_address: str, start_time: Optional[datetime] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """Get user fills (executed trades)"""
        data = {
            "type": "userFills",
            "user": user_address
        }
        
        # Add time filter if specified
        if start_time:
            data["startTime"] = int(start_time.timestamp() * 1000)  # Convert to milliseconds
        
        success, response = await self._make_request("POST", "/info", data)
        
        if success:
            fills = response if isinstance(response, list) else []
            logger.debug(f"Retrieved {len(fills)} fills for {user_address}")
            return True, fills
        else:
            logger.error(f"Failed to get fills for {user_address}: {response}")
            return False, []
    
    async def get_user_funding(self, user_address: str, start_time: Optional[datetime] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """Get user funding payments"""
        data = {
            "type": "userFunding",
            "user": user_address
        }
        
        if start_time:
            data["startTime"] = int(start_time.timestamp() * 1000)
        
        success, response = await self._make_request("POST", "/info", data)
        
        if success:
            funding = response if isinstance(response, list) else []
            logger.debug(f"Retrieved {len(funding)} funding events for {user_address}")
            return True, funding
        else:
            logger.error(f"Failed to get funding for {user_address}: {response}")
            return False, []
    
    async def batch_get_order_statuses(self, user_address: str, order_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
        """Get status of multiple orders efficiently"""
        if not order_ids:
            return {}
        
        # Get all open orders once
        success, open_orders = await self.get_open_orders(user_address)
        
        if not success:
            logger.error(f"Failed to get open orders for batch status check: {user_address}")
            return {order_id: None for order_id in order_ids}
        
        # Create lookup map
        open_orders_map = {}
        for order in open_orders:
            oid = order.get('order', {}).get('oid')
            if oid is not None:
                open_orders_map[oid] = order
        
        # Return results
        results = {}
        for order_id in order_ids:
            results[order_id] = open_orders_map.get(order_id)
        
        logger.debug(f"Batch retrieved status for {len(order_ids)} orders for {user_address}")
        return results
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for monitoring"""
        return {
            "state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "last_failure_time": self.circuit_breaker.last_failure_time.isoformat() if self.circuit_breaker.last_failure_time else None,
            "half_open_calls": self.circuit_breaker.half_open_calls
        }
    
    async def get_recent_close_fills(self, user_address: str, coin: str, minutes_back: int = 10) -> Tuple[bool, List[Dict[str, Any]]]:
        """Get recent closing fills for a specific coin to calculate accurate exit price and PnL"""
        # Get fills from the last specified minutes
        start_time = datetime.utcnow() - timedelta(minutes=minutes_back)
        success, all_fills = await self.get_user_fills(user_address, start_time)
        
        if not success:
            return False, []
        
        # Filter for closing fills of the specific coin
        close_fills = []
        for fill in all_fills:
            if (fill.get('coin') == coin and 
                fill.get('dir') in ['Close Long', 'Close Short']):
                close_fills.append(fill)
        
        # Sort by time (most recent first)
        close_fills.sort(key=lambda x: x.get('time', 0), reverse=True)
        
        logger.debug(f"Found {len(close_fills)} recent close fills for {user_address} {coin}")
        return True, close_fills
    
    async def get_meta_info(self) -> Tuple[bool, Dict[str, Any]]:
        """Get meta information including asset mappings"""
        data = {"type": "meta"}
        
        success, response = await self._make_request("POST", "/info", data)
        
        if success:
            logger.debug("Retrieved meta information successfully")
            return True, response
        else:
            logger.error(f"Failed to get meta info: {response}")
            return False, {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics for monitoring"""
        return {
            "circuit_breaker": self.get_circuit_breaker_status(),
            "recent_requests": len(self.request_timestamps),
            "session_active": self.session is not None
        }