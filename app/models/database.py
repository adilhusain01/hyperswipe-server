"""
Database models for HyperSwipe using Beanie ODM
"""
from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field


class TelegramUser(Document):
    """Telegram user mapping for notifications"""
    wallet_address: str = Field(..., description="User's wallet address (lowercase)")
    chat_id: str = Field(..., description="Telegram chat ID")
    username: Optional[str] = Field(None, description="Telegram username")
    first_name: Optional[str] = Field(None, description="Telegram first name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Whether notifications are enabled")
    
    class Settings:
        name = "telegram_users"
        indexes = [
            "wallet_address",
            "chat_id",
            [("wallet_address", 1), ("is_active", 1)]
        ]
    
    @classmethod
    async def get_by_wallet(cls, wallet_address: str) -> Optional["TelegramUser"]:
        """Get user by wallet address"""
        return await cls.find_one({"wallet_address": wallet_address.lower(), "is_active": True})
    
    @classmethod
    async def get_by_chat_id(cls, chat_id: str) -> Optional["TelegramUser"]:
        """Get user by Telegram chat ID"""
        return await cls.find_one({"chat_id": chat_id, "is_active": True})
    
    async def update_last_seen(self):
        """Update the last seen timestamp"""
        self.updated_at = datetime.utcnow()
        await self.save()


class NotificationSettings(Document):
    """User notification preferences"""
    wallet_address: str = Field(..., description="User's wallet address")
    fill_notifications: bool = Field(default=True, description="Send order fill notifications")
    pnl_notifications: bool = Field(default=True, description="Send P&L update notifications")
    liquidation_warnings: bool = Field(default=True, description="Send liquidation warnings")
    daily_summary: bool = Field(default=True, description="Send daily portfolio summary")
    min_notification_amount: float = Field(default=0.0, description="Minimum USD amount to trigger notifications")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "notification_settings"
        indexes = ["wallet_address"]
    
    @classmethod
    async def get_or_create(cls, wallet_address: str) -> "NotificationSettings":
        """Get existing settings or create new ones with defaults"""
        settings = await cls.find_one({"wallet_address": wallet_address.lower()})
        if not settings:
            settings = cls(wallet_address=wallet_address.lower())
            await settings.insert()
        return settings


class TradingStats(Document):
    """Trading statistics for analytics"""
    wallet_address: str = Field(..., description="User's wallet address")
    total_trades: int = Field(default=0, description="Total number of trades")
    total_volume: float = Field(default=0.0, description="Total trading volume in USD")
    total_pnl: float = Field(default=0.0, description="Total realized P&L in USD")
    last_trade_time: Optional[datetime] = Field(None, description="Last trade timestamp")
    notifications_sent: int = Field(default=0, description="Total notifications sent")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "trading_stats"
        indexes = [
            "wallet_address",
            [("wallet_address", 1), ("last_trade_time", -1)]
        ]
    
    @classmethod
    async def get_or_create(cls, wallet_address: str) -> "TradingStats":
        """Get existing stats or create new ones"""
        stats = await cls.find_one({"wallet_address": wallet_address.lower()})
        if not stats:
            stats = cls(wallet_address=wallet_address.lower())
            await stats.insert()
        return stats
    
    async def record_trade(self, volume: float, pnl: float = 0.0):
        """Record a new trade"""
        self.total_trades += 1
        self.total_volume += volume
        self.total_pnl += pnl
        self.last_trade_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        await self.save()
    
    async def record_notification(self):
        """Record that a notification was sent"""
        self.notifications_sent += 1
        self.updated_at = datetime.utcnow()
        await self.save()