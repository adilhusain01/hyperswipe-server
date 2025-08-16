# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HyperSwipe is a unified Python FastAPI server for cryptocurrency trading on Hyperliquid. It combines transaction signing with real-time WebSocket data streaming, replacing a dual Node.js + Python setup with a single, production-ready service.

**Key Technologies:**
- FastAPI with async WebSocket support
- Hyperliquid official Python SDK for transaction signing
- Docker containerization with nginx reverse proxy
- Pydantic models for validation
- WebSocket manager for real-time market data

## Development Commands

### Local Development
```bash
# Setup virtual environment
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install websockets  # Required for WebSocket functionality

# Run development server
python run.py
# or
uvicorn app.main:app --host 127.0.0.1 --port 8081 --reload

# Test health endpoint
curl http://localhost:8081/health

# Test WebSocket connection
wscat -c ws://localhost:8081/ws
```

### Production/Docker Commands
```bash
# Deploy with Docker (one-click deployment)
chmod +x deploy-docker.sh
./deploy-docker.sh

# Management scripts (created by deploy script)
~/start-hyperswipe.sh    # Start all services
~/stop-hyperswipe.sh     # Stop all services  
~/update-hyperswipe.sh   # Update and restart
~/logs-hyperswipe.sh     # View logs

# Docker compose commands
docker-compose ps                    # Show service status
docker-compose logs -f               # View logs
docker-compose restart nginx        # Restart nginx
docker-compose build --no-cache     # Rebuild containers
```

### Testing Commands
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests (if test files exist)
pytest

# Test coverage
pytest --cov=app
```

## Architecture Overview

### Core Components

**FastAPI Application (`app/main.py`):**
- Main application entry point with lifespan management
- Global exception handling and middleware setup
- WebSocket endpoint at `/ws` for real-time data

**WebSocket Manager (`app/websocket.py`):**
- Manages connections to Hyperliquid WebSocket API
- Broadcasts market data to connected clients
- Handles client subscriptions (user data, candles, price updates)
- Auto-reconnection logic for Hyperliquid connection

**Signing Service (`app/services/hyperliquid_signer.py`):**
- Core business logic for transaction signing using Hyperliquid SDK
- Supports order placement and cancellation
- Signature verification and validation
- Proper nonce generation and wallet management

**Configuration (`app/config.py`):**
- Centralized settings management with Pydantic
- Environment variable support with `.env` file
- CORS, security, and API configuration

### Request/Response Flow

1. **Order Signing:** Client → `/api/v1/sign-order` → HyperliquidSigner → Response
2. **Cancel Order:** Client → `/api/v1/cancel-order` → HyperliquidSigner → Response  
3. **Real-time Data:** Client WebSocket ↔ WebSocketManager ↔ Hyperliquid WebSocket
4. **Health Monitoring:** Client → `/health` → Health status response

### Data Models (`app/models.py`)

**OrderRequest:** Complete order specification with validation
- Asset index, price, size, buy/sell direction
- Order type (limit/trigger) and time-in-force
- Wallet address and private key (validated format)

**CancelOrderRequest:** Order cancellation parameters
- Asset index and order ID to cancel
- Wallet authentication

**SignatureResponse:** Standardized API response
- Success status, signature components, complete order request

### WebSocket Message Types

**Client → Server:**
```json
{"type": "subscribe_user_data", "payload": {"userAddress": "0x..."}}
{"type": "subscribe_candles", "payload": {"coin": "SOL", "interval": "1h"}}
{"type": "unsubscribe", "payload": {"subscription": {...}}}
```

**Server → Client:**
```json
{"type": "priceUpdate", "data": {"SOL": "150.25", "ETH": "2450.75"}}
{"type": "userDataUpdate", "data": {...}}
{"type": "userEvents", "data": {...}}
```

## Key Integration Points

### Hyperliquid SDK Usage
- Uses official `hyperliquid` package for all signing operations
- Proper nonce generation with timestamp milliseconds
- Signature verification using `recover_agent_or_user_from_l1_action`
- Testnet vs mainnet configuration via `is_mainnet` parameter

### Security Considerations  
- Private keys processed in-memory only, never logged or persisted
- Rate limiting (100 req/min per IP) via middleware
- CORS restrictions to authorized origins only
- Input validation with Pydantic models
- Comprehensive error handling without exposing internals

### Production Deployment
- Docker containerization with multi-service orchestration
- Nginx reverse proxy with SSL termination (Let's Encrypt)
- Health checks and auto-restart capabilities
- Centralized logging and monitoring setup
- One-click deployment script with management commands

## Environment Configuration

Key environment variables (see `.env.example`):
```bash
ENVIRONMENT=development|production
HYPERLIQUID_TESTNET=true|false
CORS_ORIGINS=comma-separated list of allowed origins
RATE_LIMIT_PER_MINUTE=100
LOG_LEVEL=INFO|DEBUG|WARNING|ERROR
```

## Common Development Patterns

### Adding New API Endpoints
1. Define Pydantic models in `app/models.py`
2. Create route handler in `app/routes/`
3. Add business logic to `app/services/`
4. Include router in `app/main.py`

### WebSocket Message Handling
1. Add message type handling in `ws_manager.handle_client_message()`
2. Implement subscription logic for new data types
3. Add corresponding broadcast methods

### Configuration Updates
1. Add new settings to `Settings` class in `app/config.py`
2. Update environment file and Docker configuration
3. Document new configuration options

This architecture supports the complete trading workflow while maintaining security, performance, and operational reliability for production cryptocurrency trading applications.