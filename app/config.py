"""
Configuration management for the HyperSwipe Signing Service
"""
import os
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8081
    reload: bool = True
    
    # CORS
    cors_origins: List[str] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Create React App
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ]
    
    # Security
    api_key_header: str = "X-API-Key"
    rate_limit_per_minute: int = 100
    
    # Hyperliquid
    hyperliquid_testnet: bool = True
    hyperliquid_base_url: str = "https://api.hyperliquid-testnet.xyz"
    
    # Logging
    log_level: str = "INFO"
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


# Global settings instance
settings = Settings()