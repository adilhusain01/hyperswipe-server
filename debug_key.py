#!/usr/bin/env python3
"""
Debug script to verify private key to address derivation
"""
from eth_account import Account

def debug_private_key():
    """Debug what address a private key derives to"""
    
    print("=== Private Key Debug ===")
    private_key = input("Enter your private key (the one from MetaMask): ").strip()
    
    # Handle with or without 0x prefix
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    try:
        wallet = Account.from_key(private_key)
        print(f"✅ Private key is valid")
        print(f"📍 Derived address: {wallet.address}")
        print(f"🎯 Expected address: 0x36fD41533d1c86225BDA5FB4E0bC0a8CD22D3180")
        
        if wallet.address.lower() == "0x36fD41533d1c86225BDA5FB4E0bC0a8CD22D3180".lower():
            print("✅ MATCH! Private key correctly derives to your MetaMask address")
        else:
            print("❌ MISMATCH! This private key does not match your MetaMask address")
            print("Please double-check you exported the correct private key from MetaMask")
            
    except Exception as e:
        print(f"❌ Error with private key: {e}")

if __name__ == "__main__":
    debug_private_key()