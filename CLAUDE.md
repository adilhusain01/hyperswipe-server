# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HyperSwipe is a unified Python FastAPI server for professional cryptocurrency trading on Hyperliquid. The application combines transaction signing, real-time WebSocket data streaming, Telegram notifications, and database persistence into a single production-ready service.

**Key Technologies:**
- FastAPI for async web framework
- Hyperliquid official Python SDK for transaction signing
- WebSocket for real-time data streaming
- MongoDB Atlas with Beanie ODM for data persistence  
- Telegram Bot API for trading notifications
- Docker with multi-stage builds for containerization
- Nginx as reverse proxy with SSL termination

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
# Edit .env with your configuration values
```

### Running the Application
```bash
# Development mode (with hot reload)
python run.py

# Or using uvicorn directly
uvicorn app.main:app --host 127.0.0.1 --port 8081 --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8081 --workers 4
```

### Docker Development
```bash
# Build and run with Docker Compose
docker-compose up --build

# Check container status
docker-compose ps

# View logs
docker-compose logs hyperswipe-server -f

# Stop all services
docker-compose down
```

### Testing and Debugging
```bash
# Health check
curl http://localhost:8081/health

# API documentation
open http://localhost:8081/docs

# Test WebSocket connection
wscat -c ws://localhost:8081/ws

# Test signing endpoint
curl -X POST http://localhost:8081/api/v1/sign-order \
  -H "Content-Type: application/json" \
  -d '{"asset_index": 0, "is_buy": true, "price": "150.25", "size": "0.1", "reduce_only": false, "order_type": "limit", "time_in_force": "Ioc", "wallet_address": "0x...", "private_key": "..."}'
```

### Database Operations
```bash
# MongoDB connection is handled automatically via app/services/database.py
# To test database connectivity, check application logs for MongoDB connection success
```

## Architecture Overview

### Application Structure
```
app/
├── main.py              # FastAPI app with WebSocket and middleware setup
├── config.py            # Environment configuration with Pydantic settings
├── middleware.py        # Security, CORS, and logging middleware
├── websocket.py         # WebSocket manager for real-time Hyperliquid data
├── models/
│   ├── database.py      # Beanie ODM models for MongoDB
│   └── pydantic_models.py # Request/response models
├── routes/
│   ├── health.py        # Health check endpoints
│   ├── signing.py       # Transaction signing endpoints
│   └── telegram.py      # Telegram bot integration
└── services/
    ├── database.py      # MongoDB connection and utilities
    ├── hyperliquid_signer.py # Official SDK transaction signing
    └── telegram.py      # Telegram notification service
```

### Key Components

**1. WebSocket Manager (`app/websocket.py`)**
- Maintains persistent connection to Hyperliquid's WebSocket API
- Handles real-time price feeds, user data, and market updates
- Manages client connections and message broadcasting
- Supports user-specific data subscriptions

**2. Transaction Signing (`app/services/hyperliquid_signer.py`)**
- Uses Hyperliquid's official Python SDK for cryptographic operations
- Handles order signing, cancellation, and validation
- Maintains security best practices for private key handling
- Supports both testnet and mainnet environments

**3. Database Layer (`app/models/database.py`)**
- MongoDB Atlas integration with Beanie ODM
- Models: TelegramUser, NotificationSettings, TradingStats
- Async database operations with proper connection management
- SSL certificate validation for secure connections

**4. Telegram Integration (`app/services/telegram.py`)**
- Professional trading notifications via Telegram bot
- Position updates, P&L alerts, liquidation warnings
- User registration and management
- Webhook handling for bot commands

### Configuration Management

Environment variables are managed through `app/config.py` using Pydantic Settings:

**Critical Environment Variables:**
- `MONGODB_URL`: MongoDB Atlas connection string with SSL
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for notifications
- `HYPERLIQUID_TESTNET`: Boolean for testnet/mainnet switching
- `CORS_ORIGINS`: Comma-separated list of allowed origins

### Production Deployment

**Docker Setup:**
- Multi-stage Dockerfile for optimized builds
- docker-compose.yml includes: app server, nginx, certbot, redis, watchtower
- Non-root user execution for security
- Health checks and automatic restarts

**Services:**
- **hyperswipe-server**: Main FastAPI application (port 8081)
- **nginx**: Reverse proxy with SSL termination (ports 80/443)
- **redis**: Caching layer for future features
- **certbot**: Automatic SSL certificate management
- **watchtower**: Automatic container updates

## Development Guidelines

### Adding New API Endpoints
1. Create route handler in `app/routes/`
2. Define Pydantic models in `app/models/pydantic_models.py`
3. Add business logic to `app/services/`
4. Include router in `app/main.py`
5. Update API documentation

### WebSocket Message Types
```python
# Client to Server
{
  "type": "subscribe_user_data",
  "payload": {"userAddress": "0x..."}
}

# Server to Client
{
  "type": "priceUpdate",
  "data": {"SOL": "150.25", "ETH": "2450.75"}
}
```

### Database Model Creation
```python
# Example new model in app/models/database.py
class NewModel(Document):
    field1: str
    field2: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        collection = "new_collection"
```

### Error Handling
- All endpoints return consistent error format: `{"success": False, "error": "message", "detail": "details"}`
- Comprehensive logging with structured messages
- Global exception handler in `app/main.py`

### Security Considerations
- Private keys processed in-memory only, never logged or stored
- Rate limiting via middleware (configurable per minute)
- CORS restrictions to authorized origins only
- Input validation through Pydantic models
- MongoDB SSL connections with certificate validation

### Common Issues and Solutions

**MongoDB SSL Errors:**
```python
# SSL certificate issues are handled in app/services/database.py
# Uses tlsAllowInvalidCertificates=false for security
```

**WebSocket Connection Issues:**
- Check CORS origins configuration
- Verify WebSocket endpoint accessibility
- Monitor connection logs in `app/websocket.py`

**Telegram Bot Not Responding:**
- Verify TELEGRAM_BOT_TOKEN in environment
- Check webhook URL configuration
- Test `/start` command handling in `app/routes/telegram.py`

## Monitoring and Maintenance

**Health Endpoints:**
- `GET /health` - Basic service health
- `GET /status` - Detailed service status including database connectivity

**Log Monitoring:**
```bash
# Application logs
docker-compose logs hyperswipe-server -f

# Nginx access logs
docker-compose logs nginx -f

# System logs
journalctl -u hyperswipe-server -f
```

**Performance Monitoring:**
- Monitor WebSocket connection count
- Track database query performance
- Monitor memory usage for WebSocket connections
- Check Telegram notification delivery rates

This application is production-ready with comprehensive error handling, security measures, and monitoring capabilities.