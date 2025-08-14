"""
Hyperliquid signing service using the official Python SDK
"""
import time
from typing import Optional, Dict, Any
from eth_account import Account
from hyperliquid.utils.signing import sign_l1_action, order_wires_to_order_action, recover_agent_or_user_from_l1_action, order_request_to_order_wire
from app.models import OrderRequest, CancelOrderRequest
import logging

logger = logging.getLogger(__name__)


class HyperliquidSigner:
    """Service for signing Hyperliquid transactions using the official SDK"""
    
    def __init__(self, is_testnet: bool = True):
        self.is_testnet = is_testnet
        logger.info(f"Initialized HyperliquidSigner (testnet: {is_testnet})")
    
    def create_order_request_dict(self, order_req: OrderRequest) -> Dict[str, Any]:
        """Convert OrderRequest to SDK OrderRequest format"""
        
        # Create order request in the format expected by the official SDK
        order_request_dict = {
            "coin": f"ASSET_{order_req.asset_index}",  # This will be converted by name_to_asset
            "is_buy": order_req.is_buy,
            "sz": float(order_req.size),
            "limit_px": float(order_req.price),
            "order_type": {
                order_req.order_type: {
                    "tif": order_req.time_in_force
                } if order_req.order_type == "limit" else {}
            },
            "reduce_only": order_req.reduce_only
        }
        
        logger.debug(f"Created order request dict: {order_request_dict}")
        return order_request_dict
    
    def create_order_wire(self, order_req: OrderRequest) -> Dict[str, Any]:
        """Convert OrderRequest to Hyperliquid order wire format using official SDK"""
        
        # Create order request dict
        order_request_dict = self.create_order_request_dict(order_req)
        
        # Use the official SDK function to create order wire with correct field ordering
        order_wire = order_request_to_order_wire(order_request_dict, order_req.asset_index)
        
        logger.debug(f"Created order wire using SDK: {order_wire}")
        return order_wire
    
    def create_order_action(self, order_req: OrderRequest) -> Dict[str, Any]:
        """Create the complete order action using official SDK"""
        
        order_wire = self.create_order_wire(order_req)
        
        # Use the official SDK function to create action with correct field ordering
        action = order_wires_to_order_action([order_wire])
        
        logger.debug(f"Created order action using SDK: {action}")
        return action
    
    def sign_order(self, order_req: OrderRequest) -> Dict[str, Any]:
        """
        Sign a Hyperliquid order using the official Python SDK
        
        Args:
            order_req: OrderRequest containing all order details
            
        Returns:
            Dict containing signature and complete order request
        """
        try:
            # Create wallet from private key
            private_key = order_req.private_key
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
                
            wallet = Account.from_key(private_key)
            logger.info(f"Created wallet for address: {wallet.address}")
            logger.info(f"Request wallet address: {order_req.wallet_address}")
            logger.info(f"Derived wallet address: {wallet.address}")
            
            # Ensure wallet address is lowercase (as per Hyperliquid requirements)
            wallet_address_lower = wallet.address.lower()
            request_address_lower = order_req.wallet_address.lower()
            
            # Verify wallet address matches
            if wallet_address_lower != request_address_lower:
                raise ValueError(f"Private key does not match wallet address. "
                               f"Expected: {request_address_lower}, "
                               f"Got: {wallet_address_lower}")
            
            # Create order action
            action = self.create_order_action(order_req)
            
            # Generate nonce (timestamp in milliseconds)
            nonce = int(time.time() * 1000)
            
            # Prepare vault address
            vault_address = order_req.vault_address if order_req.vault_address else None
            
            # Use expires_after only if explicitly provided (most orders should not have expiration)
            expires_after = order_req.expires_after
            
            # Sign using Hyperliquid SDK
            logger.info("Signing order with Hyperliquid SDK...")
            logger.info(f"Signing parameters: wallet={wallet.address}, nonce={nonce}, testnet={self.is_testnet}")
            logger.info(f"Action to sign: {action}")
            
            signature = sign_l1_action(
                wallet=wallet,
                action=action,
                active_pool=vault_address,
                nonce=nonce,
                expires_after=expires_after,
                is_mainnet=not self.is_testnet
            )
            
            logger.info(f"Generated signature: {signature}")
            
            # Verify signature recovery (for debugging)
            try:
                recovered_address = recover_agent_or_user_from_l1_action(
                    action=action,
                    signature=signature,
                    active_pool=vault_address,
                    nonce=nonce,
                    expires_after=expires_after,
                    is_mainnet=not self.is_testnet
                )
                logger.info(f"Signature verification - Original: {wallet.address}, Recovered: {recovered_address}")
                
                if recovered_address.lower() != wallet.address.lower():
                    logger.error(f"SIGNATURE MISMATCH! Original: {wallet.address}, Recovered: {recovered_address}")
                    raise ValueError(f"Signature verification failed. Address mismatch: {wallet.address} vs {recovered_address}")
                else:
                    logger.info("✅ Signature verification passed")
                    
            except Exception as e:
                logger.error(f"Signature verification error: {e}")
                raise ValueError(f"Signature verification failed: {e}")
            
            # Create complete order request for Hyperliquid API (matching official SDK format)
            order_request = {
                "action": action,
                "nonce": nonce,
                "signature": signature
            }
            
            # Only include optional fields if they have values (avoid null fields)
            if vault_address is not None:
                order_request["vaultAddress"] = vault_address
            if expires_after is not None:
                order_request["expiresAfter"] = expires_after
                
            # Debug: Log the complete request that will be sent to Hyperliquid
            logger.info(f"Complete order request for Hyperliquid: {order_request}")
            
            logger.info("Order signed successfully")
            
            return {
                "success": True,
                "signature": signature,
                "order_request": order_request,
                "wallet_address": wallet.address,
                "nonce": nonce
            }
            
        except Exception as e:
            logger.error(f"Order signing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_signature(self, action: Dict[str, Any], signature: Dict[str, Any], 
                        wallet_address: str, nonce: int, 
                        vault_address: Optional[str] = None) -> bool:
        """
        Verify that a signature is valid for the given parameters
        
        Args:
            action: The order action
            signature: The signature to verify
            wallet_address: Expected signer address
            nonce: The nonce used
            vault_address: Vault address if applicable
            
        Returns:
            bool: True if signature is valid
        """
        try:
            # This is a placeholder - in practice, you'd use Hyperliquid's
            # signature recovery functions to verify
            logger.info(f"Verifying signature for wallet: {wallet_address}")
            return True  # Simplified for now
            
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    def sign_cancel_order(self, cancel_req: CancelOrderRequest) -> Dict[str, Any]:
        """
        Sign a cancel order request using the Hyperliquid SDK
        
        Args:
            cancel_req: CancelOrderRequest containing cancel parameters and wallet info
            
        Returns:
            Dict containing success status and either signed request or error message
        """
        try:
            logger.info(f"Starting cancel order signing for {cancel_req.wallet_address}")
            
            # Create wallet from private key
            wallet = Account.from_key(cancel_req.private_key)
            logger.info(f"Created wallet with address: {wallet.address}")
            
            # Validate wallet address matches
            if wallet.address.lower() != cancel_req.wallet_address.lower():
                raise ValueError(f"Private key does not match wallet address. Expected: {cancel_req.wallet_address}, Got: {wallet.address}")
            
            # Generate nonce (timestamp in milliseconds)
            nonce = int(time.time() * 1000)
            
            # Create cancel action according to Hyperliquid API format
            cancel_action = {
                "type": "cancel",
                "cancels": [
                    {
                        "a": cancel_req.asset_index,  # asset index
                        "o": cancel_req.order_id      # order id
                    }
                ]
            }
            
            logger.info(f"Cancel action created: {cancel_action}")
            
            # Sign using Hyperliquid SDK
            logger.info("Signing cancel order with Hyperliquid SDK...")
            logger.info(f"Signing parameters: wallet={wallet.address}, nonce={nonce}, testnet={self.is_testnet}")
            
            signature = sign_l1_action(
                wallet=wallet,
                action=cancel_action,
                active_pool=None,
                nonce=nonce,
                expires_after=None,
                is_mainnet=not self.is_testnet
            )
            
            logger.info(f"Generated cancel signature: {signature}")
            
            # Create complete cancel request for Hyperliquid API
            cancel_request = {
                "action": cancel_action,
                "nonce": nonce,
                "signature": signature
            }
            
            logger.info(f"Complete cancel request for Hyperliquid: {cancel_request}")
            logger.info("Cancel order signed successfully")
            
            return {
                "success": True,
                "signature": signature,
                "order_request": cancel_request,
                "wallet_address": wallet.address,
                "nonce": nonce
            }
            
        except Exception as e:
            logger.error(f"Cancel order signing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }