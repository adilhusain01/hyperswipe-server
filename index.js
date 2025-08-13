import { WebSocketServer } from 'ws'
import WebSocket from 'ws'

const PORT = process.env.PORT || 8080
const HYPERLIQUID_WS_URL = 'wss://api.hyperliquid-testnet.xyz/ws'

class HyperSwipeServer {
  constructor() {
    this.wss = new WebSocketServer({ port: PORT })
    this.hyperliquidWs = null
    this.clients = new Set()
    this.subscriptions = new Map()
    this.reconnectInterval = null
    this.reconnectDelay = 5000 // 5 seconds
    
    this.setupServer()
    this.connectToHyperliquid()
    
    console.log(`🚀 HyperSwipe WebSocket server running on port ${PORT}`)
  }

  setupServer() {
    this.wss.on('connection', (ws) => {
      console.log('📱 Client connected')
      this.clients.add(ws)

      ws.on('message', (message) => {
        try {
          const data = JSON.parse(message.toString())
          this.handleClientMessage(ws, data)
        } catch (error) {
          console.error('❌ Invalid message from client:', error)
          ws.send(JSON.stringify({ error: 'Invalid JSON' }))
        }
      })

      ws.on('close', () => {
        console.log('📱 Client disconnected')
        this.clients.delete(ws)
      })

      ws.on('error', (error) => {
        console.error('❌ Client WebSocket error:', error)
        this.clients.delete(ws)
      })

      // Send connection confirmation
      ws.send(JSON.stringify({
        type: 'connected',
        message: 'Connected to HyperSwipe WebSocket server'
      }))
    })
  }

  connectToHyperliquid() {
    console.log('🔗 Connecting to Hyperliquid WebSocket...')
    
    this.hyperliquidWs = new WebSocket(HYPERLIQUID_WS_URL)

    this.hyperliquidWs.on('open', () => {
      console.log('✅ Connected to Hyperliquid WebSocket')
      
      // Clear reconnection attempts
      if (this.reconnectInterval) {
        clearInterval(this.reconnectInterval)
        this.reconnectInterval = null
      }

      // Subscribe to all mid prices for trading cards
      this.subscribeToHyperliquid({
        method: 'subscribe',
        subscription: { type: 'allMids' }
      })

      // Re-subscribe to any existing subscriptions
      this.resubscribeAll()
    })

    this.hyperliquidWs.on('message', (message) => {
      try {
        const data = JSON.parse(message.toString())
        this.handleHyperliquidMessage(data)
      } catch (error) {
        console.error('❌ Error parsing Hyperliquid message:', error)
      }
    })

    this.hyperliquidWs.on('close', () => {
      console.log('🔌 Disconnected from Hyperliquid WebSocket')
      this.scheduleReconnect()
    })

    this.hyperliquidWs.on('error', (error) => {
      console.error('❌ Hyperliquid WebSocket error:', error)
      this.scheduleReconnect()
    })
  }

  scheduleReconnect() {
    if (!this.reconnectInterval) {
      console.log(`⏰ Scheduling reconnect in ${this.reconnectDelay}ms`)
      this.reconnectInterval = setTimeout(() => {
        this.connectToHyperliquid()
      }, this.reconnectDelay)
    }
  }

  subscribeToHyperliquid(subscription) {
    if (this.hyperliquidWs && this.hyperliquidWs.readyState === WebSocket.OPEN) {
      console.log('📊 Subscribing to:', subscription.subscription)
      this.hyperliquidWs.send(JSON.stringify(subscription))
    } else {
      console.log('⚠️ Cannot subscribe - Hyperliquid WebSocket not connected')
    }
  }

  resubscribeAll() {
    // Re-subscribe to user-specific data for all connected clients
    for (const [userId, subs] of this.subscriptions.entries()) {
      subs.forEach(sub => {
        this.subscribeToHyperliquid(sub)
      })
    }
  }

  handleClientMessage(ws, data) {
    const { type, payload } = data

    switch (type) {
      case 'subscribe_user_data':
        this.handleUserDataSubscription(ws, payload)
        break
      
      case 'subscribe_candles':
        this.handleCandleSubscription(ws, payload)
        break
      
      case 'unsubscribe':
        this.handleUnsubscription(ws, payload)
        break
      
      default:
        console.log('❓ Unknown message type:', type)
        ws.send(JSON.stringify({ error: 'Unknown message type' }))
    }
  }

  handleUserDataSubscription(ws, { userAddress }) {
    if (!userAddress) {
      ws.send(JSON.stringify({ error: 'User address required' }))
      return
    }

    console.log('👤 Subscribing to user data for:', userAddress)

    // Subscribe to user account data
    const webDataSub = {
      method: 'subscribe',
      subscription: { type: 'webData2', user: userAddress }
    }

    // Subscribe to user events (fills, etc.)
    const userEventsSub = {
      method: 'subscribe',
      subscription: { type: 'userEvents', user: userAddress }
    }

    // Store subscriptions for this user
    if (!this.subscriptions.has(userAddress)) {
      this.subscriptions.set(userAddress, [])
    }
    this.subscriptions.get(userAddress).push(webDataSub, userEventsSub)

    // Subscribe to Hyperliquid
    this.subscribeToHyperliquid(webDataSub)
    this.subscribeToHyperliquid(userEventsSub)

    ws.send(JSON.stringify({
      type: 'subscription_confirmed',
      data: { userAddress, subscriptions: ['webData2', 'userEvents'] }
    }))
  }

  handleCandleSubscription(ws, { coin, interval }) {
    if (!coin || !interval) {
      ws.send(JSON.stringify({ error: 'Coin and interval required' }))
      return
    }

    console.log(`📈 Subscribing to candles for ${coin} ${interval}`)

    const candleSub = {
      method: 'subscribe',
      subscription: { type: 'candle', coin, interval }
    }

    this.subscribeToHyperliquid(candleSub)

    ws.send(JSON.stringify({
      type: 'subscription_confirmed',
      data: { coin, interval, subscription: 'candle' }
    }))
  }

  handleUnsubscription(ws, { subscription }) {
    console.log('🚫 Unsubscribing from:', subscription)
    
    const unsubscribeMsg = {
      method: 'unsubscribe',
      subscription
    }

    this.subscribeToHyperliquid(unsubscribeMsg)
  }

  handleHyperliquidMessage(data) {
    const { channel, data: messageData } = data

    switch (channel) {
      case 'subscriptionResponse':
        console.log('✅ Subscription confirmed:', messageData)
        break

      case 'allMids':
        this.broadcastToClients({
          type: 'price_update',
          data: messageData
        })
        break

      case 'webData2':
        this.broadcastToClients({
          type: 'user_data_update',
          data: messageData
        })
        break

      case 'userEvents':
        this.broadcastToClients({
          type: 'user_events',
          data: messageData
        })
        break

      case 'candle':
        this.broadcastToClients({
          type: 'candle_update',
          data: messageData
        })
        break

      default:
        // Forward other messages as-is
        this.broadcastToClients({
          type: 'hyperliquid_message',
          channel,
          data: messageData
        })
    }
  }

  broadcastToClients(message) {
    const messageStr = JSON.stringify(message)
    
    this.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(messageStr)
      }
    })
  }
}

// Start the server
const server = new HyperSwipeServer()

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('🛑 Shutting down server...')
  server.wss.close()
  if (server.hyperliquidWs) {
    server.hyperliquidWs.close()
  }
  process.exit(0)
})