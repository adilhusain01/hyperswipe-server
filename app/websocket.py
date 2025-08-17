"""
WebSocket service for real-time Hyperliquid data
Consolidated WebSocket + Signing server
"""
import json
import asyncio
import logging
from typing import Dict, Set
import websockets
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
import websockets.client

logger = logging.getLogger(__name__)

class HyperliquidWebSocketManager:
    """Manages WebSocket connections to Hyperliquid and client connections"""
    
    def __init__(self):
        self.hyperliquid_ws = None
        self.client_connections: Set[WebSocket] = set()
        # Track per-client subscriptions
        self.client_subscriptions: Dict[WebSocket, Dict[str, any]] = {}
        # Track which users are subscribed to prevent duplicate Hyperliquid subscriptions
        self.subscribed_users: Set[str] = set()
        self.is_connected = False
        self.reconnect_task = None
        self.hyperliquid_url = "wss://api.hyperliquid-testnet.xyz/ws"
        
    async def connect_to_hyperliquid(self):
        """Connect to Hyperliquid WebSocket"""
        try:
            logger.info("🔗 Connecting to Hyperliquid WebSocket...")
            self.hyperliquid_ws = await websockets.client.connect(self.hyperliquid_url)
            self.is_connected = True
            logger.info("✅ Connected to Hyperliquid WebSocket")
            
            # Subscribe to allMids for price updates
            await self.subscribe_to_hyperliquid({
                "method": "subscribe",
                "subscription": {"type": "allMids"}
            })
            
            # Start listening for messages
            asyncio.create_task(self.listen_to_hyperliquid())
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Hyperliquid: {e}")
            self.is_connected = False
            await self.schedule_reconnect()
    
    async def listen_to_hyperliquid(self):
        """Listen for messages from Hyperliquid WebSocket"""
        try:
            async for message in self.hyperliquid_ws:
                try:
                    data = json.loads(message)
                    await self.handle_hyperliquid_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse Hyperliquid message: {e}")
                except Exception as e:
                    logger.error(f"❌ Error handling Hyperliquid message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 Hyperliquid WebSocket connection closed")
            self.is_connected = False
            await self.schedule_reconnect()
        except Exception as e:
            logger.error(f"❌ Error in Hyperliquid listener: {e}")
            self.is_connected = False
            await self.schedule_reconnect()
    
    async def schedule_reconnect(self):
        """Schedule reconnection to Hyperliquid"""
        if self.reconnect_task and not self.reconnect_task.done():
            return
            
        logger.info("⏰ Scheduling Hyperliquid reconnection in 5 seconds...")
        self.reconnect_task = asyncio.create_task(self._reconnect())
    
    async def _reconnect(self):
        """Reconnect to Hyperliquid after delay"""
        await asyncio.sleep(5)
        await self.connect_to_hyperliquid()
    
    async def subscribe_to_hyperliquid(self, subscription):
        """Subscribe to Hyperliquid data"""
        if self.hyperliquid_ws and self.is_connected:
            try:
                await self.hyperliquid_ws.send(json.dumps(subscription))
                logger.info(f"📊 Subscribed to: {subscription['subscription']}")
            except Exception as e:
                logger.error(f"❌ Failed to subscribe: {e}")
        else:
            logger.warning("⚠️ Cannot subscribe - not connected to Hyperliquid")
    
    async def handle_hyperliquid_message(self, data):
        """Handle messages from Hyperliquid and broadcast to clients"""
        channel = data.get("channel")
        message_data = data.get("data")
        
        if channel == "allMids":
            # Broadcast price updates to all clients (public data)
            await self.broadcast_to_all_clients({
                "type": "priceUpdate",
                "data": message_data
            })
        elif channel == "webData2":
            # Send user data only to clients subscribed to this specific user
            user_address = self.extract_user_from_data(message_data)
            if user_address:
                await self.broadcast_to_user_clients(user_address, {
                    "type": "userDataUpdate", 
                    "data": message_data
                })
                
                # Send Telegram notifications for position changes
                await self.handle_position_updates_for_telegram(user_address, message_data)
            else:
                logger.warning(f"⚠️ Could not extract user from webData2: {message_data}")
        elif channel == "userEvents":
            # Send user events only to clients subscribed to this specific user
            user_address = self.extract_user_from_data(message_data)
            if user_address:
                await self.broadcast_to_user_clients(user_address, {
                    "type": "userEvents",
                    "data": message_data
                })
                
                # Send to order tracking service
                await self._forward_to_order_tracking(user_address, message_data)
                
                # Send Telegram notifications for fills
                await self.handle_user_events_for_telegram(user_address, message_data)
            else:
                logger.warning(f"⚠️ Could not extract user from userEvents: {message_data}")
        elif channel == "subscriptionResponse":
            logger.info(f"✅ Subscription confirmed: {message_data}")
        else:
            # Forward other messages to all clients
            await self.broadcast_to_all_clients({
                "type": "hyperliquidMessage",
                "channel": channel,
                "data": message_data
            })
    
    def extract_user_from_data(self, data) -> str:
        """Extract user address from Hyperliquid message data"""
        if isinstance(data, dict):
            # Try different possible locations for user address
            user = data.get('user') or data.get('userAddress')
            if user:
                return user.lower()
            
            # Check nested structures
            if 'clearinghouseState' in data:
                return self.extract_user_from_data(data['clearinghouseState'])
            
            # Check if there's a fills array with user info
            if 'fills' in data and data['fills']:
                fill = data['fills'][0]
                user = fill.get('user') or fill.get('userAddress')
                if user:
                    return user.lower()
        
        return None
    
    async def broadcast_to_all_clients(self, message):
        """Broadcast message to all connected clients (for public data)"""
        if not self.client_connections:
            return
            
        message_str = json.dumps(message)
        disconnected_clients = set()
        
        for client in self.client_connections:
            try:
                if client.client_state == WebSocketState.CONNECTED:
                    await client.send_text(message_str)
                else:
                    disconnected_clients.add(client)
            except Exception as e:
                logger.warning(f"⚠️ Failed to send to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        await self._cleanup_disconnected_clients(disconnected_clients)
    
    async def broadcast_to_user_clients(self, user_address: str, message):
        """Broadcast message only to clients subscribed to specific user"""
        if not self.client_connections:
            return
        
        message_str = json.dumps(message)
        disconnected_clients = set()
        sent_count = 0
        
        for client in self.client_connections:
            try:
                if client.client_state == WebSocketState.CONNECTED:
                    # Check if this client is subscribed to this user
                    client_subs = self.client_subscriptions.get(client, {})
                    if client_subs.get('userAddress') == user_address:
                        await client.send_text(message_str)
                        sent_count += 1
                else:
                    disconnected_clients.add(client)
            except Exception as e:
                logger.warning(f"⚠️ Failed to send user data to client: {e}")
                disconnected_clients.add(client)
        
        logger.debug(f"📤 Sent user data for {user_address} to {sent_count} clients")
        await self._cleanup_disconnected_clients(disconnected_clients)
    
    async def _cleanup_disconnected_clients(self, disconnected_clients):
        """Clean up disconnected clients and their subscriptions"""
        for client in disconnected_clients:
            await self.remove_client(client)
    
    async def add_client(self, websocket: WebSocket):
        """Add a new client connection"""
        await websocket.accept()
        self.client_connections.add(websocket)
        logger.info(f"📱 Client connected. Total clients: {len(self.client_connections)}")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "Connected to HyperSwipe WebSocket server"
        }))
    
    async def remove_client(self, websocket: WebSocket):
        """Remove a client connection and clean up subscriptions"""
        self.client_connections.discard(websocket)
        
        # Clean up client subscriptions
        if websocket in self.client_subscriptions:
            client_subs = self.client_subscriptions[websocket]
            user_address = client_subs.get('userAddress')
            
            # Check if any other clients are still subscribed to this user
            if user_address:
                still_subscribed = any(
                    subs.get('userAddress') == user_address 
                    for client, subs in self.client_subscriptions.items() 
                    if client != websocket and client in self.client_connections
                )
                
                if not still_subscribed:
                    # No other clients subscribed to this user - unsubscribe from Hyperliquid
                    await self.unsubscribe_user_from_hyperliquid(user_address)
                    self.subscribed_users.discard(user_address)
                    logger.info(f"🚫 Unsubscribed {user_address} from Hyperliquid (no more clients)")
            
            del self.client_subscriptions[websocket]
            
        logger.info(f"📱 Client disconnected. Total clients: {len(self.client_connections)}")
    
    async def handle_client_message(self, websocket: WebSocket, message: str):
        """Handle messages from clients"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            payload = data.get("payload", {})
            
            if message_type == "subscribe_user_data":
                await self.handle_user_data_subscription(websocket, payload)
            elif message_type == "unsubscribe_user_data":
                await self.handle_user_data_unsubscription(websocket, payload)
            elif message_type == "subscribe_candles":
                await self.handle_candle_subscription(websocket, payload)
            elif message_type == "unsubscribe":
                await self.handle_unsubscription(websocket, payload)
            else:
                logger.warning(f"❓ Unknown message type: {message_type}")
                await websocket.send_text(json.dumps({
                    "error": "Unknown message type"
                }))
                
        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON from client")
            await websocket.send_text(json.dumps({
                "error": "Invalid JSON"
            }))
        except Exception as e:
            logger.error(f"❌ Error handling client message: {e}")
    
    async def handle_user_data_subscription(self, websocket: WebSocket, payload):
        """Handle user data subscription with proper client isolation"""
        user_address = payload.get("userAddress")
        if not user_address:
            await websocket.send_text(json.dumps({
                "error": "User address required"
            }))
            return
        
        user_address = user_address.lower()  # Normalize address
        logger.info(f"👤 Client subscribing to user data for: {user_address}")
        
        # Remove previous subscription for this client if exists
        if websocket in self.client_subscriptions:
            old_user = self.client_subscriptions[websocket].get('userAddress')
            if old_user and old_user != user_address:
                logger.info(f"🔄 Client switching from {old_user} to {user_address}")
                # Clean up old subscription if no other clients use it
                await self._cleanup_user_subscription(old_user, websocket)
        
        # Store client subscription
        self.client_subscriptions[websocket] = {
            'userAddress': user_address,
            'subscriptions': ['webData2', 'userEvents']
        }
        
        # Only subscribe to Hyperliquid if not already subscribed for this user
        if user_address not in self.subscribed_users:
            logger.info(f"📡 New user subscription - subscribing to Hyperliquid for: {user_address}")
            
            # Force subscribe to userEvents FIRST (critical for fill notifications)
            subscriptions = [
                {
                    "method": "subscribe", 
                    "subscription": {"type": "userEvents", "user": user_address}
                },
                {
                    "method": "subscribe",
                    "subscription": {"type": "webData2", "user": user_address}
                }
            ]
            
            for sub in subscriptions:
                logger.error(f"🚨 CRITICAL: Attempting subscription: {sub}")
                await self.subscribe_to_hyperliquid(sub)
                logger.error(f"🚨 CRITICAL: Subscription attempt completed for: {sub}")
            
            self.subscribed_users.add(user_address)
        else:
            logger.info(f"📡 User {user_address} already subscribed in Hyperliquid - reusing subscription")
        
        await websocket.send_text(json.dumps({
            "type": "subscription_confirmed",
            "data": {
                "userAddress": user_address,
                "subscriptions": ["webData2", "userEvents"]
            }
        }))
    
    async def _cleanup_user_subscription(self, user_address: str, excluding_client: WebSocket = None):
        """Check if user subscription can be cleaned up"""
        still_subscribed = any(
            subs.get('userAddress') == user_address 
            for client, subs in self.client_subscriptions.items() 
            if client != excluding_client and client in self.client_connections
        )
        
        if not still_subscribed and user_address in self.subscribed_users:
            await self.unsubscribe_user_from_hyperliquid(user_address)
            self.subscribed_users.discard(user_address)
            logger.info(f"🚫 Cleaned up Hyperliquid subscription for {user_address}")
    
    async def unsubscribe_user_from_hyperliquid(self, user_address: str):
        """Unsubscribe user from Hyperliquid"""
        unsubscriptions = [
            {
                "method": "unsubscribe",
                "subscription": {"type": "webData2", "user": user_address}
            },
            {
                "method": "unsubscribe", 
                "subscription": {"type": "userEvents", "user": user_address}
            }
        ]
        
        for unsub in unsubscriptions:
            await self.subscribe_to_hyperliquid(unsub)  # Note: using same method for unsub
    
    async def handle_user_data_unsubscription(self, websocket: WebSocket, payload):
        """Handle user data unsubscription"""
        user_address = payload.get("userAddress")
        if not user_address:
            await websocket.send_text(json.dumps({
                "error": "User address required"
            }))
            return
        
        user_address = user_address.lower()
        logger.info(f"🚫 Client unsubscribing from user data for: {user_address}")
        
        # Remove client subscription
        if websocket in self.client_subscriptions:
            client_subs = self.client_subscriptions[websocket]
            if client_subs.get('userAddress') == user_address:
                del self.client_subscriptions[websocket]
                
                # Check if we need to unsubscribe from Hyperliquid
                await self._cleanup_user_subscription(user_address, websocket)
                
                await websocket.send_text(json.dumps({
                    "type": "unsubscription_confirmed",
                    "data": {
                        "userAddress": user_address,
                        "unsubscribed": ["webData2", "userEvents"]
                    }
                }))
    
    async def handle_candle_subscription(self, websocket: WebSocket, payload):
        """Handle candle data subscription"""
        coin = payload.get("coin")
        interval = payload.get("interval", "1h")
        
        if not coin:
            await websocket.send_text(json.dumps({
                "error": "Coin required"
            }))
            return
        
        logger.info(f"📈 Subscribing to candles for {coin} {interval}")
        
        subscription = {
            "method": "subscribe",
            "subscription": {"type": "candle", "coin": coin, "interval": interval}
        }
        
        await self.subscribe_to_hyperliquid(subscription)
        
        await websocket.send_text(json.dumps({
            "type": "subscription_confirmed",
            "data": {"coin": coin, "interval": interval, "subscription": "candle"}
        }))
    
    async def handle_unsubscription(self, websocket: WebSocket, payload):
        """Handle unsubscription"""
        subscription = payload.get("subscription")
        if subscription:
            unsubscribe_msg = {
                "method": "unsubscribe",
                "subscription": subscription
            }
            await self.subscribe_to_hyperliquid(unsubscribe_msg)
            logger.info(f"🚫 Unsubscribed from: {subscription}")
    
    async def handle_user_events_for_telegram(self, user_address: str, data):
        """Handle user events and send Telegram notifications"""
        try:
            from app.services.telegram import get_telegram_service
            
            telegram_service = get_telegram_service()
            if not telegram_service:
                return
            
            # Check if user has registered their Telegram integration
            chat_id = await telegram_service.get_user_chat_id(user_address)
            if not chat_id:
                logger.debug(f"🔍 No Telegram chat ID registered for {user_address} - skipping notifications")
                return
            
            # Get user notification settings and trading stats
            from app.models.database import NotificationSettings, TradingStats
            notification_settings = await NotificationSettings.get_or_create(user_address)
            trading_stats = await TradingStats.get_or_create(user_address)
            
            # Check if fill notifications are enabled
            if not notification_settings.fill_notifications:
                logger.debug(f"🔕 Fill notifications disabled for {user_address} - skipping")
                return
            
            # Check if this is a fill event
            if isinstance(data, dict) and 'fills' in data:
                fills = data['fills']
                if fills and isinstance(fills, list):
                    # Initialize position tracking for this user
                    if not hasattr(self, 'user_position_tracker'):
                        self.user_position_tracker = {}
                    
                    user_tracker_key = f"tracker_{user_address}"
                    if user_tracker_key not in self.user_position_tracker:
                        self.user_position_tracker[user_tracker_key] = {}
                    
                    user_tracker = self.user_position_tracker[user_tracker_key]
                    
                    for fill in fills:
                        # Extract fill information with validation
                        coin = fill.get('coin', 'Unknown')
                        side = fill.get('side', 'Unknown')  # 'B' for buy, 'S' for sell
                        px = float(fill.get('px', '0'))
                        sz = float(fill.get('sz', '0'))
                        fee = float(fill.get('fee', '0'))
                        fill_time = fill.get('time', 0)
                        
                        # Calculate trade volume
                        trade_volume = px * sz
                        
                        # Store this fill in our permanent fill history for accurate exit price calculation
                        if not hasattr(self, 'user_fill_history'):
                            self.user_fill_history = {}
                        
                        fill_history_key = f"fills_{user_address}"
                        if fill_history_key not in self.user_fill_history:
                            self.user_fill_history[fill_history_key] = []
                        
                        # Store the fill with timestamp for position close analysis
                        self.user_fill_history[fill_history_key].append({
                            'coin': coin,
                            'side': side,
                            'px': px,
                            'sz': sz,
                            'fee': fee,
                            'time': fill_time,
                            'volume': trade_volume
                        })
                        
                        # Keep only recent fills (last 1000 fills per user)
                        if len(self.user_fill_history[fill_history_key]) > 1000:
                            self.user_fill_history[fill_history_key] = self.user_fill_history[fill_history_key][-1000:]
                        
                        logger.info(f"📊 FILL EVENT: {user_address} {coin} {side} {sz}@${px} vol=${trade_volume:.2f}")
                        
                        # Track position changes based on fills
                        if coin not in user_tracker:
                            user_tracker[coin] = {
                                'net_size': 0.0,
                                'avg_entry_price': 0.0,
                                'total_cost': 0.0,
                                'fills': []
                            }
                        
                        position = user_tracker[coin]
                        prev_size = position['net_size']
                        
                        # Update position based on fill side
                        if side == 'B':  # Buy/Long
                            position['total_cost'] += trade_volume
                            position['net_size'] += sz
                            if position['net_size'] > 0:
                                position['avg_entry_price'] = position['total_cost'] / position['net_size']
                        elif side == 'S':  # Sell/Short
                            if prev_size > 0:  # Closing long position
                                close_size = min(sz, prev_size)
                                # Calculate PnL for the closed portion
                                realized_pnl = close_size * (px - position['avg_entry_price'])
                                
                                # Send position close notification
                                if close_size == prev_size:  # Full close
                                    await self.send_position_close_notification(
                                        user_address, coin, telegram_service, trading_stats,
                                        notification_settings, close_size, position['avg_entry_price'], 
                                        px, realized_pnl, full_close=True
                                    )
                                else:  # Partial close
                                    await self.send_position_close_notification(
                                        user_address, coin, telegram_service, trading_stats,
                                        notification_settings, close_size, position['avg_entry_price'], 
                                        px, realized_pnl, full_close=False
                                    )
                                
                                # Update position
                                position['net_size'] -= close_size
                                if position['net_size'] <= 0:
                                    position['total_cost'] = 0.0
                                    position['avg_entry_price'] = 0.0
                                else:
                                    position['total_cost'] *= (position['net_size'] / prev_size)
                                
                                remaining_size = sz - close_size
                                if remaining_size > 0:
                                    # Opening short position with remaining size
                                    position['net_size'] = -remaining_size
                                    position['total_cost'] = remaining_size * px
                                    position['avg_entry_price'] = px
                            else:  # Opening or increasing short position
                                position['total_cost'] += trade_volume
                                position['net_size'] -= sz
                                if position['net_size'] < 0:
                                    position['avg_entry_price'] = position['total_cost'] / abs(position['net_size'])
                        
                        # Store fill details
                        position['fills'].append({
                            'side': side,
                            'price': px,
                            'size': sz,
                            'fee': fee,
                            'time': fill_time,
                            'volume': trade_volume
                        })
                        
                        # Send fill notification for ALL fills (no threshold - every fill is important)
                        await telegram_service.send_position_fill_alert(user_address, {
                            'coin': coin,
                            'side': side,  # Use the original 'B' or 'S' format that the telegram service expects
                            'px': str(px),
                            'sz': str(sz),
                            'fee': str(fee)
                        })
                        
                        await trading_stats.record_notification()
                        logger.info(f"✅ Sent fill notification: {coin} {side} {sz}@${px}")
                        
                        # Always record trade stats
                        await trading_stats.record_trade(volume=trade_volume, pnl=0.0)
                        
                        # Log current position state
                        logger.info(f"📊 Position after fill: {coin} size={position['net_size']:.4f} avg_price=${position['avg_entry_price']:.4f}")
                        
        except Exception as e:
            logger.error(f"❌ Error processing user events for Telegram: {e}", exc_info=True)
    
    async def send_position_close_notification(self, user_address: str, coin: str, telegram_service, 
                                             trading_stats, notification_settings, close_size: float,
                                             entry_price: float, exit_price: float, realized_pnl: float,
                                             full_close: bool = True):
        """Send position close notification with accurate data"""
        try:
            # Check minimum notification amount
            if abs(realized_pnl) >= notification_settings.min_notification_amount:
                close_type = "Full" if full_close else "Partial"
                logger.info(f"🔔 {close_type} position close: {user_address} {coin} size={close_size:.4f} PnL=${realized_pnl:.2f}")
                
                # Create accurate close notification data
                close_notification_data = {
                    'coin': coin,
                    'szi': '0' if full_close else str(-close_size),  # Negative for sell
                    'unrealizedPnl': str(realized_pnl),
                    'entryPx': str(entry_price),
                    'markPrice': str(exit_price),
                    'closedSize': str(close_size),
                    'fullClose': full_close,
                    'positionClosed': True
                }
                
                # Send notification
                await telegram_service.send_pnl_alert(user_address, close_notification_data)
                await trading_stats.record_notification()
                
                logger.info(f"✅ Sent {close_type.lower()} position close notification for {user_address}: {coin}")
            else:
                logger.debug(f"🔕 Position close PnL ${realized_pnl:.2f} below threshold ${notification_settings.min_notification_amount}")
                
        except Exception as e:
            logger.error(f"❌ Error sending position close notification: {e}")
    
    async def handle_position_updates_for_telegram(self, user_address: str, data):
        """Handle position updates and send Telegram notifications for significant PnL changes and position closes"""
        try:
            from app.services.telegram import get_telegram_service
            
            telegram_service = get_telegram_service()
            if not telegram_service:
                return
            
            # Check if user has registered their Telegram integration
            chat_id = await telegram_service.get_user_chat_id(user_address)
            if not chat_id:
                logger.debug(f"🔍 No Telegram chat ID registered for {user_address} - skipping notifications")
                return
            
            # Get user notification settings and trading stats
            from app.models.database import NotificationSettings, TradingStats
            notification_settings = await NotificationSettings.get_or_create(user_address)
            trading_stats = await TradingStats.get_or_create(user_address)
            
            # Check if PnL notifications are enabled
            if not notification_settings.pnl_notifications:
                logger.debug(f"🔕 PnL notifications disabled for {user_address}")
                return
            
            logger.info(f"📱 Processing position updates for registered Telegram user {user_address}")
            
            # Extract clearinghouse state
            clearinghouse_state = data.get('clearinghouseState', data)
            if not clearinghouse_state:
                return
            
            # Get asset positions
            asset_positions = clearinghouse_state.get('assetPositions', [])
            logger.info(f"🔍 Found {len(asset_positions)} asset positions for {user_address}")
            
            # Initialize position tracking if not exists
            if not hasattr(self, 'user_positions'):
                self.user_positions = {}
            if not hasattr(self, 'sent_notifications'):
                self.sent_notifications = set()
            
            # Track current positions
            current_positions = {}
            
            # Get previous positions for comparison
            user_key = f"positions_{user_address}"
            previous_positions = self.user_positions.get(user_key, {})
            logger.info(f"🔍 Previous positions: {list(previous_positions.keys())}")
            
            # If we have no asset positions now, but had some before, those were closed
            if not asset_positions and previous_positions:
                logger.info(f"🔔 All positions closed for {user_address} - sending notifications")
                for coin, prev_pos in previous_positions.items():
                    prev_size = prev_pos.get('size', 0)
                    if prev_size > 0:
                        # Position was closed - send notification with accurate exit price
                        prev_pnl = prev_pos.get('unrealized_pnl', 0)
                        prev_entry_px = prev_pos.get('entry_px', 0)
                        prev_position_size = prev_size
                        
                        # Get accurate exit price and PnL from Hyperliquid API
                        exit_price = prev_entry_px  # fallback
                        actual_closed_size = prev_position_size
                        realized_pnl = prev_pnl  # fallback
                        
                        try:
                            # Get recent close fills from API for accurate data
                            from app.services.hyperliquid_api_client import HyperliquidAPIClient
                            api_client = HyperliquidAPIClient("https://api.hyperliquid-testnet.xyz", is_testnet=True)
                            await api_client.start()
                            
                            success, close_fills = await api_client.get_recent_close_fills(user_address, coin, minutes_back=10)
                            
                            if success and close_fills:
                                # Get the most recent close fill
                                latest_close = close_fills[0]
                                exit_price = float(latest_close.get('px', prev_entry_px))
                                actual_closed_size = float(latest_close.get('sz', prev_position_size))
                                realized_pnl = float(latest_close.get('closedPnl', prev_pnl))
                                
                                logger.info(f"✅ Got accurate close data from API: {coin} exit=${exit_price:.4f} size={actual_closed_size:.4f} PnL=${realized_pnl:.4f}")
                            else:
                                logger.warning(f"⚠️ No recent close fills found via API for {coin}, using fallback values")
                            
                            await api_client.stop()
                            
                        except Exception as api_error:
                            logger.error(f"❌ Failed to get close fills from API: {api_error}")
                            # Continue with fallback values
                        
                        logger.info(f"🔔 Position closed for {user_address}: {coin} entry=${prev_entry_px:.4f} exit=${exit_price:.4f} size={actual_closed_size:.4f} PnL=${realized_pnl:.4f}")
                        
                        # Create close notification data with accurate prices and PnL
                        close_notification_data = {
                            'coin': coin,
                            'szi': '0',
                            'unrealizedPnl': str(realized_pnl),  # Use accurate realized PnL from API
                            'entryPx': str(prev_entry_px),
                            'markPrice': str(exit_price),
                            'closedSize': str(actual_closed_size),
                            'fullClose': True,
                            'positionClosed': True
                        }
                        
                        # Check minimum notification amount using accurate PnL
                        if abs(realized_pnl) >= notification_settings.min_notification_amount:
                            # Send position close notification
                            await telegram_service.send_pnl_alert(user_address, close_notification_data)
                            
                            # Record notification in stats
                            await trading_stats.record_notification()
                            
                            logger.info(f"✅ Sent position close notification for {user_address}: {coin}")
                        else:
                            logger.debug(f"🔕 Position close PnL ${realized_pnl:.4f} below threshold ${notification_settings.min_notification_amount} for {user_address}")
                
                # Clear stored positions since all are closed
                self.user_positions[user_key] = {}
                return
            
            # Skip processing if no positions to track
            if not asset_positions:
                logger.debug(f"🔍 No asset positions to process for {user_address}")
                return
            
            # Check each position for significant PnL changes and track for close detection
            for position in asset_positions:
                if isinstance(position, dict) and 'position' in position:
                    pos_data = position['position']
                    
                    # Extract position details
                    coin = pos_data.get('coin', '')
                    szi = pos_data.get('szi', '0')
                    unrealized_pnl = float(pos_data.get('unrealizedPnl', 0))
                    entry_px = float(pos_data.get('entryPx', 0))
                    
                    position_size = abs(float(szi))
                    
                    logger.info(f"📊 Processing position: {coin} size={position_size} PnL=${unrealized_pnl:.2f}")
                    
                    # Store current position state
                    current_positions[coin] = {
                        'size': position_size,
                        'unrealized_pnl': unrealized_pnl,
                        'entry_px': entry_px,
                        'data': pos_data
                    }
                    
                    # Only process active positions for PnL alerts
                    if position_size > 0 and entry_px > 0:
                        position_value = position_size * entry_px
                        pnl_percentage = (unrealized_pnl / position_value) * 100 if position_value > 0 else 0
                        
                        # Send notification for significant PnL changes (±10%, ±25%, ±50%)
                        significant_thresholds = [10, 25, 50]
                        abs_pnl_pct = abs(pnl_percentage)
                        
                        for threshold in significant_thresholds:
                            if abs_pnl_pct >= threshold:
                                # Store the notification state to avoid spam
                                notification_key = f"{user_address}_{coin}_{threshold}"
                                
                                if notification_key not in self.sent_notifications:
                                    # Check minimum notification amount
                                    if abs(unrealized_pnl) >= notification_settings.min_notification_amount:
                                        logger.info(f"📊 Sending PnL alert for {user_address}: {coin} {pnl_percentage:+.1f}%")
                                        
                                        # Add current mark price for better formatting
                                        enhanced_position_data = {
                                            **pos_data,
                                            'markPrice': pos_data.get('markPrice', entry_px)  # Use entry price as fallback
                                        }
                                        
                                        await telegram_service.send_pnl_alert(user_address, enhanced_position_data)
                                        
                                        # Record notification in stats
                                        await trading_stats.record_notification()
                                        
                                        # Mark as sent to prevent duplicates
                                        self.sent_notifications.add(notification_key)
                                        
                                        logger.info(f"✅ Sent PnL threshold alert for {user_address}: {coin}")
                                    else:
                                        logger.debug(f"🔕 PnL ${unrealized_pnl:.2f} below threshold ${notification_settings.min_notification_amount} for {user_address}")
                                    
                                    # Only send for the highest threshold reached
                                    break
            
            # Check for individual position closes (compare with previous state)
            # Note: user_key and previous_positions already defined above
            
            for coin, prev_pos in previous_positions.items():
                current_pos = current_positions.get(coin)
                
                # Position was closed if it had size before but now has 0 or doesn't exist
                prev_size = prev_pos.get('size', 0)
                current_size = current_pos.get('size', 0) if current_pos else 0
                
                if prev_size > 0 and current_size == 0:
                    # Position was closed - send notification with accurate exit price
                    prev_pnl = prev_pos.get('unrealized_pnl', 0)
                    prev_entry_px = prev_pos.get('entry_px', 0)
                    prev_position_size = prev_size
                    
                    # Get accurate exit price and PnL from Hyperliquid API
                    exit_price = prev_entry_px  # fallback
                    actual_closed_size = prev_position_size
                    realized_pnl = prev_pnl  # fallback
                    
                    try:
                        # Get recent close fills from API for accurate data
                        from app.services.hyperliquid_api_client import HyperliquidAPIClient
                        api_client = HyperliquidAPIClient("https://api.hyperliquid-testnet.xyz", is_testnet=True)
                        await api_client.start()
                        
                        success, close_fills = await api_client.get_recent_close_fills(user_address, coin, minutes_back=10)
                        
                        if success and close_fills:
                            # Get the most recent close fill
                            latest_close = close_fills[0]
                            exit_price = float(latest_close.get('px', prev_entry_px))
                            actual_closed_size = float(latest_close.get('sz', prev_position_size))
                            realized_pnl = float(latest_close.get('closedPnl', prev_pnl))
                            
                            logger.info(f"✅ Got accurate close data from API: {coin} exit=${exit_price:.4f} size={actual_closed_size:.4f} PnL=${realized_pnl:.4f}")
                        else:
                            logger.warning(f"⚠️ No recent close fills found via API for {coin}, using fallback values")
                        
                        await api_client.stop()
                        
                    except Exception as api_error:
                        logger.error(f"❌ Failed to get close fills from API: {api_error}")
                        # Continue with fallback values
                    
                    logger.info(f"🔔 Individual position closed for {user_address}: {coin} entry=${prev_entry_px:.4f} exit=${exit_price:.4f} size={actual_closed_size:.4f} PnL=${realized_pnl:.4f}")
                    
                    # Create close notification data with accurate prices and PnL
                    close_notification_data = {
                        'coin': coin,
                        'szi': '0',  # Position is now closed
                        'unrealizedPnl': str(realized_pnl),  # Use accurate realized PnL from API
                        'entryPx': str(prev_entry_px),
                        'markPrice': str(exit_price),  # Accurate exit price
                        'closedSize': str(actual_closed_size),
                        'fullClose': True,
                        'positionClosed': True  # Flag to indicate this is a close notification
                    }
                    
                    # Check minimum notification amount using accurate PnL
                    if abs(realized_pnl) >= notification_settings.min_notification_amount:
                        # Send position close notification
                        await telegram_service.send_pnl_alert(user_address, close_notification_data)
                        
                        # Record notification in stats
                        await trading_stats.record_notification()
                        
                        logger.info(f"✅ Sent individual position close notification for {user_address}: {coin}")
                    else:
                        logger.debug(f"🔕 Individual position close PnL ${realized_pnl:.4f} below threshold ${notification_settings.min_notification_amount} for {user_address}")
                    
                    # Clear related PnL threshold notifications for this position
                    keys_to_remove = [key for key in self.sent_notifications 
                                    if key.startswith(f"{user_address}_{coin}_")]
                    for key in keys_to_remove:
                        self.sent_notifications.discard(key)
                        
                    logger.info(f"✅ Sent position close notification for {user_address}: {coin}")
            
            # Update stored positions for next comparison
            self.user_positions[user_key] = current_positions
                        
        except Exception as e:
            logger.error(f"❌ Error processing position updates for Telegram: {e}")
    
    async def _forward_to_order_tracking(self, user_address: str, message_data):
        """Forward WebSocket events to the order tracking service"""
        try:
            from app.services.order_tracking_service import get_order_tracking_service
            
            order_tracking_service = get_order_tracking_service()
            if order_tracking_service:
                await order_tracking_service.handle_websocket_event(user_address, message_data)
                logger.debug(f"Forwarded WebSocket event to order tracking for {user_address}")
            else:
                logger.debug("Order tracking service not available - skipping event forwarding")
                
        except Exception as e:
            logger.error(f"Error forwarding WebSocket event to order tracking: {e}")
    
    async def subscribe_telegram_users_to_userevents(self):
        """Auto-subscribe all Telegram users to userEvents for fill notifications"""
        logger.info("🔕 Auto-subscription disabled - using normal WebSocket subscription flow")
        return

# Global WebSocket manager instance
ws_manager = HyperliquidWebSocketManager()