"""
MongoDB Atlas database service for HyperSwipe
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings
from app.models.database import TelegramUser, NotificationSettings, TradingStats

logger = logging.getLogger(__name__)


class DatabaseService:
    """MongoDB Atlas connection and management"""
    
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.database = None
        
    async def connect(self):
        """Connect to MongoDB Atlas"""
        try:
            if not settings.mongodb_url:
                logger.warning("⚠️ MongoDB URL not configured - running without persistence")
                return False
                
            # Configure MongoDB client with SSL settings  
            self.client = AsyncIOMotorClient(
                settings.mongodb_url,
                tls=True,
                tlsAllowInvalidCertificates=True,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000
            )
            
            # Test the connection
            await self.client.admin.command('ping')
            logger.info("✅ Connected to MongoDB Atlas")
            
            # Get database
            self.database = self.client[settings.mongodb_database]
            
            # Initialize Beanie ODM
            await init_beanie(
                database=self.database,
                document_models=[
                    TelegramUser,
                    NotificationSettings, 
                    TradingStats
                ]
            )
            
            logger.info(f"🗄️ Initialized database: {settings.mongodb_database}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB Atlas: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from MongoDB Atlas"""
        if self.client:
            self.client.close()
            logger.info("🔌 Disconnected from MongoDB Atlas")
    
    async def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            if not self.client:
                return False
            await self.client.admin.command('ping')
            return True
        except Exception:
            return False


# Global database service instance
db_service = DatabaseService()


async def init_database():
    """Initialize database connection"""
    success = await db_service.connect()
    if success:
        logger.info("🚀 Database service initialized")
    else:
        logger.warning("⚠️ Database service not available - continuing without persistence")
    return success


async def cleanup_database():
    """Cleanup database connection"""
    await db_service.disconnect()