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
        self.subscriptions: Dict[str, list] = {}
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
            # Broadcast price updates
            await self.broadcast_to_clients({
                "type": "priceUpdate",
                "data": message_data
            })
        elif channel == "webData2":
            # Broadcast user data updates
            await self.broadcast_to_clients({
                "type": "userDataUpdate", 
                "data": message_data
            })
        elif channel == "userEvents":
            # Broadcast user events
            await self.broadcast_to_clients({
                "type": "userEvents",
                "data": message_data
            })
        elif channel == "subscriptionResponse":
            logger.info(f"✅ Subscription confirmed: {message_data}")
        else:
            # Forward other messages
            await self.broadcast_to_clients({
                "type": "hyperliquidMessage",
                "channel": channel,
                "data": message_data
            })
    
    async def broadcast_to_clients(self, message):
        """Broadcast message to all connected clients"""
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
        self.client_connections -= disconnected_clients
    
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
        """Remove a client connection"""
        self.client_connections.discard(websocket)
        logger.info(f"📱 Client disconnected. Total clients: {len(self.client_connections)}")
    
    async def handle_client_message(self, websocket: WebSocket, message: str):
        """Handle messages from clients"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            payload = data.get("payload", {})
            
            if message_type == "subscribe_user_data":
                await self.handle_user_data_subscription(websocket, payload)
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
        """Handle user data subscription"""
        user_address = payload.get("userAddress")
        if not user_address:
            await websocket.send_text(json.dumps({
                "error": "User address required"
            }))
            return
        
        logger.info(f"👤 Subscribing to user data for: {user_address}")
        
        # Subscribe to webData2 and userEvents
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
        
        # Store subscription for this user
        if user_address not in self.subscriptions:
            self.subscriptions[user_address] = []
        self.subscriptions[user_address].extend(subscriptions)
        
        await websocket.send_text(json.dumps({
            "type": "subscription_confirmed",
            "data": {
                "userAddress": user_address,
                "subscriptions": ["webData2", "userEvents"]
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

# Global WebSocket manager instance
ws_manager = HyperliquidWebSocketManager()