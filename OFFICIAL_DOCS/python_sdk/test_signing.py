#!/usr/bin/env python3
"""
Test script to compare our signing with the official Hyperliquid SDK
"""
import sys
import os
sys.path.append('/Users/adilhusain/Documents/HyperSwipe')

from eth_account import Account
from hyperliquid.utils.signing import sign_l1_action, recover_agent_or_user_from_l1_action
import time

def test_signing():
    # Use the same parameters from your logs
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
    
    # Use the same nonce from your logs for comparison
    nonce = 1755110682168
    vault_address = None
    expires_after = None
    is_testnet = True
    
    print(f"\nSigning parameters:")
    print(f"Action: {action}")
    print(f"Nonce: {nonce}")
    print(f"Vault address: {vault_address}")
    print(f"Expires after: {expires_after}")
    print(f"Is testnet: {is_testnet}")
    
    # Sign with official SDK
    signature = sign_l1_action(
        wallet=wallet,
        action=action,
        active_pool=vault_address,
        nonce=nonce,
        expires_after=expires_after,
        is_mainnet=not is_testnet
    )
    
    print(f"\nGenerated signature: {signature}")
    
    # Verify signature recovery
    recovered_address = recover_agent_or_user_from_l1_action(
        action=action,
        signature=signature,
        active_pool=vault_address,
        nonce=nonce,
        expires_after=expires_after,
        is_mainnet=not is_testnet
    )
    
    print(f"\nSignature verification:")
    print(f"Original address: {wallet.address}")
    print(f"Recovered address: {recovered_address}")
    print(f"Match: {wallet.address.lower() == recovered_address.lower()}")
    
    # Create the complete order request
    order_request = {
        "action": action,
        "nonce": nonce,
        "signature": signature,
        "vaultAddress": vault_address,
        "expiresAfter": expires_after
    }
    
    print(f"\nComplete order request:")
    import json
    print(json.dumps(order_request, indent=2))
    
    # Test with different nonce (current time)
    print(f"\n" + "="*50)
    print("Testing with current timestamp nonce:")
    
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
    
    print(f"New signature: {signature2}")
    print(f"Recovered address: {recovered_address2}")
    print(f"Match: {wallet.address.lower() == recovered_address2.lower()}")

if __name__ == "__main__":
    test_signing()