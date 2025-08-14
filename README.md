# HyperSwipe Unified Server

**Unified Python server** for HyperSwipe trading application - combining transaction signing with real-time WebSocket data streaming using Hyperliquid's official SDK.

## 🚀 Key Features

- **🔐 Transaction Signing**: Secure Hyperliquid order signing using official Python SDK
- **📡 Real-time WebSocket**: Live price feeds, user data, and market updates
- **🏗️ Unified Architecture**: Single server replacing dual Node.js + Python setup
- **⚡ High Performance**: FastAPI with async WebSocket support
- **🛡️ Production Ready**: Rate limiting, CORS, comprehensive logging

## 🏗️ Architecture

```
signing-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application with WebSocket
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic data models
│   ├── middleware.py        # Security & logging middleware
│   ├── websocket.py         # WebSocket manager for real-time data
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py        # Health check endpoints
│   │   └── signing.py       # Signing API endpoints
│   └── services/
│       ├── __init__.py
│       └── hyperliquid_signer.py  # Core signing logic
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore patterns
├── run.py                  # Application entry point
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
cd /Users/adilhusain/Documents/HyperSwipe/server

# Create virtual environment
python3 -m venv env
source env/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies (including websockets for real-time data)
pip install -r requirements.txt
pip install websockets  # Required for WebSocket functionality
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration as needed
nano .env
```

### 3. Run the Unified Server

```bash
# Development mode (recommended)
source venv/bin/activate && python run.py

# Or using uvicorn directly
uvicorn app.main:app --host 127.0.0.1 --port 8081 --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8081 --workers 4
```

### 4. Test the Service

```bash
# Health check
curl http://localhost:8081/health

# WebSocket connection test
wscat -c ws://localhost:8081/ws

# API documentation
open http://localhost:8081/docs
```

### 5. Connect Frontend

Update your frontend WebSocket connection to:
```javascript
// client/src/services/websocket.js
const serverUrl = 'ws://localhost:8081/ws'  // Unified server
```

## 📡 API Endpoints

### Health & Status
- `GET /health` - Service health check
- `GET /status` - Detailed service status
- `GET /docs` - Interactive API documentation

### Signing
- `POST /api/v1/sign-order` - Sign Hyperliquid order
- `POST /api/v1/verify-signature` - Verify signature (debugging)

### WebSocket Real-time Data
- `WS /ws` - **Main WebSocket endpoint for real-time data**
  - 📊 Live price updates (allMids)
  - 👤 User account data (webData2)
  - 🎯 User events and fills (userEvents)
  - 📈 Candlestick data (candles)

#### WebSocket Message Types

**Client to Server:**
```json
{
  "type": "subscribe_user_data",
  "payload": { "userAddress": "0x..." }
}
```

**Server to Client:**
```json
{
  "type": "priceUpdate",
  "data": { "SOL": "150.25", "ETH": "2450.75" }
}
```

## 🔧 Configuration

Environment variables (see `.env.example`):

```bash
# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO

# Server
HOST=127.0.0.1
PORT=8081
RELOAD=true

# Security  
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
RATE_LIMIT_PER_MINUTE=100

# Hyperliquid
HYPERLIQUID_TESTNET=true
HYPERLIQUID_BASE_URL=https://api.hyperliquid-testnet.xyz
```

## 🔒 Security Features

- **Rate Limiting**: 100 requests per minute per IP
- **CORS Protection**: Restricted to authorized origins
- **Input Validation**: Comprehensive Pydantic validation
- **Error Handling**: Secure error responses
- **Logging**: Complete request/response logging
- **Memory Safety**: Private keys processed in-memory only

## 📊 Usage Example

### JavaScript/React Integration

```javascript
// Sign an order
const signOrder = async (orderData) => {
  const response = await fetch('http://localhost:8081/api/v1/sign-order', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      asset_index: 0,
      is_buy: true,
      price: "150.25",
      size: "0.1",
      reduce_only: false,
      order_type: "limit",
      time_in_force: "Ioc",
      wallet_address: "0x...",
      private_key: "your_private_key"
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    // Send result.order_request to Hyperliquid API
    return result.order_request;
  } else {
    throw new Error(result.error);
  }
};
```

### Response Format

```json
{
  "success": true,
  "signature": {
    "r": "0x...",
    "s": "0x...", 
    "v": 27
  },
  "order_request": {
    "action": {
      "type": "order",
      "orders": [...],
      "grouping": "na"
    },
    "nonce": 1234567890,
    "signature": {...}
  }
}
```

## 🛠️ Development

### Project Structure

- **`app/main.py`**: FastAPI application with middleware setup
- **`app/config.py`**: Centralized configuration management
- **`app/models.py`**: Pydantic models for request/response validation
- **`app/services/hyperliquid_signer.py`**: Core signing logic using Hyperliquid SDK
- **`app/routes/`**: API route handlers
- **`app/middleware.py`**: Security and logging middleware

### Adding New Features

1. **New API endpoint**: Add route in `app/routes/`
2. **New data models**: Define in `app/models.py`
3. **New business logic**: Add service in `app/services/`
4. **Configuration**: Update `app/config.py`

### Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Test coverage
pytest --cov=app
```

## 🚦 Monitoring

### Health Checks

```bash
# Basic health
curl http://localhost:8081/health

# Detailed status
curl http://localhost:8081/status
```

### Logs

Logs are output to stdout with configurable levels:
- `DEBUG`: Detailed debugging information
- `INFO`: General operational messages
- `WARNING`: Warning conditions
- `ERROR`: Error conditions

## 🔄 Integration with React Frontend

The unified server seamlessly integrates with your React frontend:

1. **📱 Single Connection**: Frontend connects to one server (`ws://localhost:8081/ws`)
2. **🔐 Secure Signing**: Transaction signing via REST API (`/api/v1/sign-order`)
3. **📡 Real-time Data**: Live prices and user data via WebSocket
4. **💰 Data Consistency**: Eliminates balance sync issues between components
5. **🚀 Simplified Architecture**: Replaces dual Node.js + Python servers

### Migration from Dual Servers

**Before:** Node.js (port 8080) + Python (port 8081)
```javascript
// Old setup - two connections
const wsUrl = 'ws://localhost:8080'      // Node.js WebSocket
const apiUrl = 'http://localhost:8081'   // Python signing
```

**After:** Unified Python Server (port 8081)
```javascript
// New setup - single connection  
const wsUrl = 'ws://localhost:8081/ws'   // Unified WebSocket + API
const apiUrl = 'http://localhost:8081'   // Same server
```

This eliminates data synchronization issues and improves reliability.

## 📈 Production Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt && \
    pip install websockets

# Copy application
COPY app/ ./app/
COPY run.py .

EXPOSE 8081
CMD ["python", "run.py"]
```

### Systemd Service

```ini
[Unit]
Description=HyperSwipe Unified Server
After=network.target

[Service]
Type=simple
User=hyperswipe
WorkingDirectory=/opt/hyperswipe-signing
ExecStart=/opt/hyperswipe-signing/venv/bin/python run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 🆕 What's New in Unified Server

### ✅ Improvements Over Dual-Server Setup

- **🔧 Single Point of Truth**: One server handles all data, eliminating sync issues
- **📊 Consistent Balances**: TradingCard and Positions show identical account values
- **🚀 Better Performance**: Reduced network overhead and connection complexity
- **🛠️ Easier Debugging**: Single log stream for all operations
- **📦 Simplified Deployment**: One service to manage instead of two

### 🔄 Migration Benefits

- **No Frontend Changes**: Existing React components work unchanged
- **Same API Interface**: All existing signing endpoints preserved
- **Enhanced WebSocket**: More reliable real-time data streaming
- **Backwards Compatible**: Easy rollback if needed

## 🤝 Support

For issues and questions:
- **📚 API Docs**: Visit `/docs` for interactive documentation
- **🔍 WebSocket Test**: Use `wscat -c ws://localhost:8081/ws`
- **📋 Health Check**: Monitor with `/health` endpoint
- **📝 Logs**: Check console output for detailed error information
- **⚙️ Config**: Verify `.env` file settings

### Common Issues

1. **WebSocket Connection Failed**: Ensure `websockets` package is installed
2. **CORS Errors**: Check `CORS_ORIGINS` in environment configuration
3. **Port Conflicts**: Verify port 8081 is available
4. **Missing Dependencies**: Run `pip install websockets` manually if needed