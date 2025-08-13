```jsx
<PrivyProvider 
  appId="your-privy-app-id"
  config={{
  "appearance": {
    "accentColor": "#6A6FF5",
    "theme": "#222224",
    "showWalletLoginFirst": false,
    "logo": "https://auth.privy.io/logos/privy-logo-dark.png",
    "walletChainType": "ethereum-and-solana",
    "walletList": [
      "detected_wallets",
      "metamask",
      "phantom",
      "coinbase_wallet",
      "base_account",
      "rainbow",
      "solflare",
      "backpack",
      "okx_wallet",
      "wallet_connect"
    ]
  },
  "loginMethods": [
    "email",
    "wallet",
    "google"
  ],
  "fundingMethodConfig": {
    "moonpay": {
      "useSandbox": true
    }
  },
  "embeddedWallets": {
    "requireUserPasswordOnCreate": false,
    "showWalletUIs": true,
    "ethereum": {
      "createOnLogin": "users-without-wallets"
    },
    "solana": {
      "createOnLogin": "off"
    }
  },
  "mfa": {
    "noPromptOnMfaRequired": false
  },
  "externalWallets": {
    "solana": {
      "connectors": {}
    }
  }
}}
>
  {children}
</PrivyProvider>
```