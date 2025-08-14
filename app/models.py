"""
Pydantic models for request/response validation
"""
from typing import Optional, Union, Literal
from pydantic import BaseModel, Field, validator


class OrderRequest(BaseModel):
    """Request model for order signing"""
    
    # Order parameters
    asset_index: int = Field(..., ge=0, description="Asset index for the perpetual")
    is_buy: bool = Field(..., description="True for buy/long, False for sell/short")
    price: Union[str, float] = Field(..., description="Limit price for the order")
    size: Union[str, float] = Field(..., description="Order size")
    reduce_only: bool = Field(False, description="Whether this is a reduce-only order")
    
    # Order type
    order_type: Literal["limit", "trigger"] = Field("limit", description="Order type")
    time_in_force: Literal["Gtc", "Ioc", "Alo"] = Field("Ioc", description="Time in force")
    
    # Wallet information
    wallet_address: str = Field(..., min_length=42, max_length=42, description="Ethereum wallet address")
    private_key: str = Field(..., min_length=64, max_length=66, description="Private key for signing")
    
    # Optional parameters
    vault_address: Optional[str] = Field(None, description="Vault address if applicable")
    expires_after: Optional[int] = Field(None, description="Expiration timestamp")
    
    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if not v.startswith('0x'):
            raise ValueError('Wallet address must start with 0x')
        if len(v) != 42:
            raise ValueError('Wallet address must be 42 characters long')
        return v.lower()
    
    @validator('private_key')
    def validate_private_key(cls, v):
        # Remove 0x prefix if present
        if v.startswith('0x'):
            v = v[2:]
        if len(v) != 64:
            raise ValueError('Private key must be 64 characters long (32 bytes)')
        return v
    
    @validator('vault_address')
    def validate_vault_address(cls, v):
        if v is not None:
            if not v.startswith('0x'):
                raise ValueError('Vault address must start with 0x')
            if len(v) != 42:
                raise ValueError('Vault address must be 42 characters long')
            return v.lower()
        return v


class CancelOrderRequest(BaseModel):
    """Request model for cancel order signing"""
    
    # Cancel parameters
    asset_index: int = Field(..., ge=0, description="Asset index for the perpetual")
    order_id: int = Field(..., description="Order ID to cancel")
    
    # Wallet information
    wallet_address: str = Field(..., min_length=42, max_length=42, description="Ethereum wallet address")
    private_key: str = Field(..., min_length=64, max_length=66, description="Private key for signing")
    
    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if not v.startswith('0x'):
            raise ValueError('Wallet address must start with 0x')
        if len(v) != 42:
            raise ValueError('Wallet address must be 42 characters long')
        return v.lower()
    
    @validator('private_key')
    def validate_private_key(cls, v):
        # Remove 0x prefix if present
        if v.startswith('0x'):
            v = v[2:]
        if len(v) != 64:
            raise ValueError('Private key must be 64 characters long (32 bytes)')
        return v


class SignatureResponse(BaseModel):
    """Response model for signed transactions"""
    
    success: bool = Field(..., description="Whether signing was successful")
    signature: Optional[dict] = Field(None, description="Signature components (r, s, v)")
    order_request: Optional[dict] = Field(None, description="Complete order request for Hyperliquid API")
    error: Optional[str] = Field(None, description="Error message if signing failed")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "signature": {
                    "r": "0x...",
                    "s": "0x...",
                    "v": 27
                },
                "order_request": {
                    "action": {...},
                    "nonce": 1234567890,
                    "signature": {...}
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str = Field("healthy", description="Service health status")
    version: str = Field("1.0.0", description="Service version")
    environment: str = Field(..., description="Current environment")
    hyperliquid_testnet: bool = Field(..., description="Whether using Hyperliquid testnet")


class ErrorResponse(BaseModel):
    """Error response model"""
    
    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code for programmatic handling")
    details: Optional[dict] = Field(None, description="Additional error details")