"""
HyperSwipe Signing Service
FastAPI application for signing Hyperliquid transactions
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.middleware import SecurityMiddleware, LoggingMiddleware
from app.routes import health, signing, telegram, order_tracking
from app.websocket import ws_manager
from app.services.telegram import initialize_telegram_service, cleanup_telegram_service
from app.services.database import init_database, cleanup_database
from app.services.order_tracking_service import initialize_order_tracking_service, cleanup_order_tracking_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("🚀 Starting HyperSwipe Signing Service")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Hyperliquid Testnet: {settings.hyperliquid_testnet}")
    logger.info(f"CORS Origins: {settings.cors_origins}")
    
    # Initialize database
    await init_database()
    
    # Start WebSocket connection to Hyperliquid
    await ws_manager.connect_to_hyperliquid()
    logger.info("📡 WebSocket manager initialized")
    
    # Initialize Telegram service
    telegram_token = getattr(settings, 'telegram_bot_token', None)
    if telegram_token:
        await initialize_telegram_service(telegram_token)
        logger.info("🤖 Telegram service initialized")
    else:
        logger.warning("⚠️ Telegram bot token not configured")
    
    # Initialize order tracking service
    try:
        await initialize_order_tracking_service(
            settings.hyperliquid_base_url, 
            settings.hyperliquid_testnet
        )
        logger.info("📊 Order tracking service initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize order tracking service: {e}")
        # Continue without order tracking
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down HyperSwipe Signing Service")
    
    # Cleanup order tracking service
    await cleanup_order_tracking_service()
    logger.info("📊 Order tracking service stopped")
    
    # Cleanup Telegram service
    await cleanup_telegram_service()
    logger.info("🤖 Telegram service stopped")
    
    # Cleanup database
    await cleanup_database()
    
    if ws_manager.hyperliquid_ws:
        await ws_manager.hyperliquid_ws.close()
        logger.info("🔌 Hyperliquid WebSocket connection closed")


# Create FastAPI application
app = FastAPI(
    title="HyperSwipe Signing Service",
    description="""
    Professional signing service for HyperSwipe trading application.
    
    This service provides secure transaction signing for Hyperliquid perpetual 
    futures trading using the official Python SDK. It handles all cryptographic 
    operations while maintaining security best practices.
    
    ## Features
    
    * **Secure Signing**: Uses Hyperliquid's official Python SDK
    * **Rate Limiting**: Built-in protection against abuse
    * **CORS Support**: Configured for frontend integration
    * **Health Monitoring**: Comprehensive health checks
    * **Error Handling**: Detailed error responses
    * **Logging**: Complete request/response logging
    
    ## Security
    
    * Private keys are processed in-memory only
    * Rate limiting prevents abuse
    * CORS restricts access to authorized origins
    * Comprehensive input validation
    """,
    version="1.0.0",
    contact={
        "name": "HyperSwipe Team",
        "email": "support@hyperswipe.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityMiddleware, api_key_header=settings.api_key_header)

# Include routers
app.include_router(health.router)
app.include_router(signing.router)
app.include_router(telegram.router)
app.include_router(order_tracking.router)

# WebSocket endpoints
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time data"""
    logger.info("📱 New WebSocket connection attempt")
    
    try:
        await ws_manager.add_client(websocket)
        
        while True:
            try:
                # Receive messages from client
                message = await websocket.receive_text()
                await ws_manager.handle_client_message(websocket, message)
            except WebSocketDisconnect:
                logger.info("📱 Client disconnected normally")
                break
            except Exception as e:
                logger.error(f"❌ Error in WebSocket communication: {e}")
                break
    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {e}")
    finally:
        await ws_manager.remove_client(websocket)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        }
    )


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirect to docs"""
    return {
        "service": "HyperSwipe Signing Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )