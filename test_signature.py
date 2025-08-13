#!/usr/bin/env python3
"""
Test script to compare our signing with the official Hyperliquid SDK
"""
from eth_account import Account
from hyperliquid.utils.signing import sign_l1_action, recover_agent_or_user_from_l1_action
import time
import json

def test_signing():
    # Use a dummy private key for testing (replace with your actual key for real test)
    print("Testing signature generation and recovery...")
    print("This will help identify if there's a parameter mismatch.")
    
    # You can paste your private key here temporarily for testing
    # DO NOT commit this to git!
    private_key = input("Enter your private key (will not be stored): ").strip()
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    wallet = Account.from_key(private_key)
    print(f"Wallet address: {wallet.address}")
    
    # Create the exact same order action from your logs
    action = {
        'type': 'order',
        'orders': [{
            'a': 0,
            'b': True,
            'p': '208.981500',
            's': '0.05',
            'r': False,
            't': {'limit': {'tif': 'Ioc'}}
        }],
        'grouping': 'na'
    }
    
    # Test with the same nonce from your logs
    test_nonce = 1755110682168
    vault_address = None
    expires_after = None
    is_testnet = True
    
    print(f"\nTest 1: Using nonce from your logs")
    print(f"Nonce: {test_nonce}")
    
    # Sign with official SDK
    signature1 = sign_l1_action(
        wallet=wallet,
        action=action,
        active_pool=vault_address,
        nonce=test_nonce,
        expires_after=expires_after,
        is_mainnet=not is_testnet
    )
    
    print(f"Generated signature: {signature1}")
    
    # Verify signature recovery
    recovered_address1 = recover_agent_or_user_from_l1_action(
        action=action,
        signature=signature1,
        active_pool=vault_address,
        nonce=test_nonce,
        expires_after=expires_after,
        is_mainnet=not is_testnet
    )
    
    print(f"Original address: {wallet.address}")
    print(f"Recovered address: {recovered_address1}")
    print(f"Match: {wallet.address.lower() == recovered_address1.lower()}")
    
    # Test with current time nonce
    print(f"\nTest 2: Using current timestamp")
    current_nonce = int(time.time() * 1000)
    print(f"Current nonce: {current_nonce}")
    
    signature2 = sign_l1_action(
        wallet=wallet,
        action=action,
        active_pool=vault_address,
        nonce=current_nonce,
        expires_after=expires_after,
        is_mainnet=not is_testnet
    )
    
    recovered_address2 = recover_agent_or_user_from_l1_action(
        action=action,
        signature=signature2,
        active_pool=vault_address,
        nonce=current_nonce,
        expires_after=expires_after,
        is_mainnet=not is_testnet
    )
    
    print(f"Generated signature: {signature2}")
    print(f"Recovered address: {recovered_address2}")
    print(f"Match: {wallet.address.lower() == recovered_address2.lower()}")
    
    # Show what the complete order request should look like
    print(f"\nComplete order request format:")
    order_request = {
        "action": action,
        "nonce": current_nonce,
        "signature": signature2,
        "vaultAddress": vault_address,
        "expiresAfter": expires_after
    }
    
    print(json.dumps(order_request, indent=2))

if __name__ == "__main__":
    test_signing()