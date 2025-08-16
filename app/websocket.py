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
            
            subscriptions = [
                {
                    "method": "subscribe",
                    "subscription": {"type": "webData2", "user": user_address}
                },
                {
                    "method": "subscribe", 
                    "subscription": {"type": "userEvents", "user": user_address}
                }
            ]
            
            for sub in subscriptions:
                await self.subscribe_to_hyperliquid(sub)
            
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
        """Handle user events and send Telegram notifications for fills"""
        try:
            from app.services.telegram import get_telegram_service
            
            telegram_service = get_telegram_service()
            if not telegram_service:
                return
            
            # Check if this is a fill event
            if isinstance(data, dict) and 'fills' in data:
                fills = data['fills']
                if fills and isinstance(fills, list):
                    for fill in fills:
                        # Extract fill information
                        coin = fill.get('coin', 'Unknown')
                        side = fill.get('side', 'Unknown')
                        px = fill.get('px', '0')
                        sz = fill.get('sz', '0')
                        fee = fill.get('fee', '0')
                        
                        logger.info(f"📈 Processing fill notification for {user_address}: {coin} {side} {sz}@{px}")
                        
                        # Send Telegram notification
                        await telegram_service.send_position_fill_alert(user_address, {
                            'coin': coin,
                            'side': side,
                            'px': px,
                            'sz': sz,
                            'fee': fee
                        })
                        
                        logger.info(f"✅ Sent Telegram fill notification for {user_address}")
                        
        except Exception as e:
            logger.error(f"❌ Error sending Telegram notification: {e}")

# Global WebSocket manager instance
ws_manager = HyperliquidWebSocketManager()