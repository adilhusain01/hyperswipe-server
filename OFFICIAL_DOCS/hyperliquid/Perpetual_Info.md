---
description: >-
  The section documents the info endpoints that are specific to perpetuals. See
  Rate limits section for rate limiting logic and weights.
---

# Perpetuals

## Retrieve all perpetual dexs

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                   | Type   | Description |
| -------------------------------------- | ------ | ----------- |
| type<mark style="color:red;">\*</mark> | String | "perpDexs"  |

{% tabs %}
{% tab title="200: OK Successful Response" %}
```json
[
  null,
  {
    "name": "test",
    "full_name": "test dex",
    "deployer": "0x5e89b26d8d66da9888c835c9bfcc2aa51813e152",
    "oracle_updater": null
  }
]
```
{% endtab %}
{% endtabs %}

## Retrieve perpetuals metadata (universe and margin tables)

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                   | Type   | Description                                                                      |
| -------------------------------------- | ------ | -------------------------------------------------------------------------------- |
| type<mark style="color:red;">\*</mark> | String | "meta"                                                                           |
| dex                                    | String | Perp dex name. Defaults to the empty string which represents the first perp dex. |

{% tabs %}
{% tab title="200: OK Successful Response" %}
```json
{
    "universe": [
        {
            "name": "BTC",
            "szDecimals": 5,
            "maxLeverage": 50
        },
        {
            "name": "ETH",
            "szDecimals": 4,
            "maxLeverage": 50
        },
        {
            "name": "HPOS",
            "szDecimals": 0,
            "maxLeverage": 3,
            "onlyIsolated": true
        },
        {
            "name": "LOOM",
            "szDecimals": 1,
            "maxLeverage": 3,
            "onlyIsolated": true,
            "isDelisted": true
        }
    ],
    "marginTables": [
        [
            50,
            {
                "description": "",
                "marginTiers": [
                    {
                        "lowerBound": "0.0",
                        "maxLeverage": 50
                    }
                ]
            }
        ],
        [
            51,
            {
                "description": "tiered 10x",
                "marginTiers": [
                    {
                        "lowerBound": "0.0",
                        "maxLeverage": 10
                    },
                    {
                        "lowerBound": "3000000.0",
                        "maxLeverage": 5
                    }
                ]
            }
        ]
    ]
}
```
{% endtab %}
{% endtabs %}

## Retrieve perpetuals asset contexts (includes mark price, current funding, open interest, etc.)

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                   | Type   | Description        |
| -------------------------------------- | ------ | ------------------ |
| type<mark style="color:red;">\*</mark> | String | "metaAndAssetCtxs" |

{% tabs %}
{% tab title="200: OK Successful Response" %}
```json
[
{
     "universe": [
        {
            "name": "BTC",
            "szDecimals": 5,
            "maxLeverage": 50
        },
        {
            "name": "ETH",
            "szDecimals": 4,
            "maxLeverage": 50
        },
        {
            "name": "HPOS",
            "szDecimals": 0,
            "maxLeverage": 3,
            "onlyIsolated": true
        }
    ]
},
[
    {
        "dayNtlVlm":"1169046.29406",
         "funding":"0.0000125",
         "impactPxs":[
            "14.3047",
            "14.3444"
         ],
         "markPx":"14.3161",
         "midPx":"14.314",
         "openInterest":"688.11",
         "oraclePx":"14.32",
         "premium":"0.00031774",
         "prevDayPx":"15.322"
    },
    {
         "dayNtlVlm":"1426126.295175",
         "funding":"0.0000125",
         "impactPxs":[
            "6.0386",
            "6.0562"
         ],
         "markPx":"6.0436",
         "midPx":"6.0431",
         "openInterest":"1882.55",
         "oraclePx":"6.0457",
         "premium":"0.00028119",
         "prevDayPx":"6.3611"
      },
      {
         "dayNtlVlm":"809774.565507",
         "funding":"0.0000125",
         "impactPxs":[
            "8.4505",
            "8.4722"
         ],
         "markPx":"8.4542",
         "midPx":"8.4557",
         "openInterest":"2912.05",
         "oraclePx":"8.4585",
         "premium":"0.00033694",
         "prevDayPx":"8.8097"
      }
]
]
```
{% endtab %}
{% endtabs %}

## Retrieve user's perpetuals account summary

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

See a user's open positions and margin summary for perpetuals trading

#### Headers

| Name                                           | Type | Description        |
| ---------------------------------------------- | ---- | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> |      | "application/json" |

#### Request Body

| Name                                   | Type   | Description                                                                                          |
| -------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------- |
| type<mark style="color:red;">\*</mark> | String | "clearinghouseState"                                                                                 |
| user<mark style="color:red;">\*</mark> | String | Onchain address in 42-character hexadecimal format; e.g. 0x0000000000000000000000000000000000000000. |
| dex                                    | String | Perp dex name. Defaults to the empty string which represents the first perp dex.                     |

{% tabs %}
{% tab title="200: OK Successful Response" %}


```json
{
  "assetPositions": [
    {
      "position": {
        "coin": "ETH",
        "cumFunding": {
          "allTime": "514.085417",
          "sinceChange": "0.0",
          "sinceOpen": "0.0"
        },
        "entryPx": "2986.3",
        "leverage": {
          "rawUsd": "-95.059824",
          "type": "isolated",
          "value": 20
        },
        "liquidationPx": "2866.26936529",
        "marginUsed": "4.967826",
        "maxLeverage": 50,
        "positionValue": "100.02765",
        "returnOnEquity": "-0.0026789",
        "szi": "0.0335",
        "unrealizedPnl": "-0.0134"
      },
      "type": "oneWay"
    }
  ],
  "crossMaintenanceMarginUsed": "0.0",
  "crossMarginSummary": {
    "accountValue": "13104.514502",
    "totalMarginUsed": "0.0",
    "totalNtlPos": "0.0",
    "totalRawUsd": "13104.514502"
  },
  "marginSummary": {
    "accountValue": "13109.482328",
    "totalMarginUsed": "4.967826",
    "totalNtlPos": "100.02765",
    "totalRawUsd": "13009.454678"
  },
  "time": 1708622398623,
  "withdrawable": "13104.514502"
}
```
{% endtab %}
{% endtabs %}

## Retrieve a user's funding history or non-funding ledger updates

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

Note: Non-funding ledger updates include deposits, transfers, and withdrawals.

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                        | Type   | Description                                                                                  |
| ------------------------------------------- | ------ | -------------------------------------------------------------------------------------------- |
| type<mark style="color:red;">\*</mark>      | String | "userFunding" or "userNonFundingLedgerUpdates"                                               |
| user<mark style="color:red;">\*</mark>      | String | Address in 42-character hexadecimal format; e.g. 0x0000000000000000000000000000000000000000. |
| startTime<mark style="color:red;">\*</mark> | int    | Start time in milliseconds, inclusive                                                        |
| endTime                                     | int    | End time in milliseconds, inclusive. Defaults to current time.                               |

{% tabs %}
{% tab title="200: OK Successful Response" %}
```json
[
    {
        "delta": {
            "coin":"ETH",
            "fundingRate":"0.0000417",
            "szi":"49.1477",
            "type":"funding",
            "usdc":"-3.625312"
        },
        "hash":"0xa166e3fa63c25663024b03f2e0da011a00307e4017465df020210d3d432e7cb8",
        "time":1681222254710
    },
    ...
]
```
{% endtab %}
{% endtabs %}



## Retrieve historical funding rates

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                        | Type   | Description                                                    |
| ------------------------------------------- | ------ | -------------------------------------------------------------- |
| type<mark style="color:red;">\*</mark>      | String | "fundingHistory"                                               |
| coin<mark style="color:red;">\*</mark>      | String | Coin, e.g. "ETH"                                               |
| startTime<mark style="color:red;">\*</mark> | int    | Start time in milliseconds, inclusive                          |
| endTime                                     | int    | End time in milliseconds, inclusive. Defaults to current time. |

{% tabs %}
{% tab title="200: OK" %}
<pre class="language-json"><code class="lang-json">[
    {
        "coin":"ETH",
        "fundingRate": "-0.00022196",
        "premium": "-0.00052196",
        "time":1683849600076
<strong>    }
</strong>]
</code></pre>
{% endtab %}
{% endtabs %}

## Retrieve predicted funding rates for different venues

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                   | Type   | Description         |
| -------------------------------------- | ------ | ------------------- |
| type<mark style="color:red;">\*</mark> | String | "predictedFundings" |

{% tabs %}
{% tab title="200: OK Successful Response" %}
```json
[
  [
    "AVAX",
    [
      [
        "BinPerp",
        {
          "fundingRate": "0.0001",
          "nextFundingTime": 1733961600000
        }
      ],
      [
        "HlPerp",
        {
          "fundingRate": "0.0000125",
          "nextFundingTime": 1733958000000
        }
      ],
      [
        "BybitPerp",
        {
          "fundingRate": "0.0001",
          "nextFundingTime": 1733961600000
        }
      ]
    ]
  ],...
]
```
{% endtab %}
{% endtabs %}

## Query perps at open interest caps

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                   | Type   | Description              |
| -------------------------------------- | ------ | ------------------------ |
| type<mark style="color:red;">\*</mark> | String | "perpsAtOpenInterestCap" |

{% tabs %}
{% tab title="200: OK Successful Response" %}
```json
["BADGER","CANTO","FTM","LOOM","PURR"]
```
{% endtab %}
{% endtabs %}

## Retrieve information about the Perp Deploy Auction

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                   | Type   | Description               |
| -------------------------------------- | ------ | ------------------------- |
| type<mark style="color:red;">\*</mark> | String | "perpDeployAuctionStatus" |

{% tabs %}
{% tab title="200: OK Successful Response" %}
```json
{
  "startTimeSeconds": 1747656000,
  "durationSeconds": 111600,
  "startGas": "500.0",
  "currentGas": "500.0",
  "endGas": null
}
```
{% endtab %}
{% endtabs %}

## Retrieve User's Active Asset Data

<mark style="color:green;">`POST`</mark> `https://api.hyperliquid.xyz/info`

#### Headers

| Name                                           | Type   | Description        |
| ---------------------------------------------- | ------ | ------------------ |
| Content-Type<mark style="color:red;">\*</mark> | String | "application/json" |

#### Request Body

| Name                                   | Type   | Description                                                                                                                                         |
| -------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| type<mark style="color:red;">\*</mark> | String | "activeAssetData"                                                                                                                                   |
| user<mark style="color:red;">\*</mark> | String | Address in 42-character hexadecimal format; e.g. 0x0000000000000000000000000000000000000000.                                                        |
| coin<mark style="color:red;">\*</mark> | String | Coin, e.g. "ETH". See [here](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#perpetuals-vs-spot) for more details. |

{% tabs %}
{% tab title="200: OK" %}
```json
{
  "user": "0xb65822a30bbaaa68942d6f4c43d78704faeabbbb",
  "coin": "APT",
  "leverage": {
    "type": "cross",
    "value": 3
  },
  "maxTradeSzs": ["24836370.4400000013", "24836370.4400000013"],
  "availableToTrade": ["37019438.0284740031", "37019438.0284740031"],
  "markPx": "4.4716"
}
```


  endpoint -> https://api.hyperliquid-testnet.xyz/info, in body -> {
      "type": "userFills",
      "user": "0x36fD41533d1c86225BDA5FB4E0bC0a8CD22D3180"
  } , output -> [
      {
          "coin": "ETH",
          "px": "4414.9",
          "sz": "0.0227",
          "side": "A",
          "time": 1755371191858,
          "startPosition": "0.0227",
          "dir": "Close Long",
          "closedPnl": "0.03405",
          "hash": "0x23df8a33e79d1ff20d280418dadad1010400b76ddc74259ecb89882dda2bb768",
          "oid": 37688457474,
          "crossed": true,
          "fee": "0.045098",
          "tid": 522854775870738,
          "feeToken": "USDC",
          "twapId": null
      },{
          "coin": "ETH",
          "px": "4413.4",
          "sz": "0.0227",
          "side": "B",
          "time": 1755370974227,
          "startPosition": "0.0",
          "dir": "Open Long",
          "closedPnl": "0.0",
          "hash": "0x91211fb62258a172be220418dad5b4010d00c312cd84950a1012aeaab1ec475d",
          "oid": 37688405638,
          "crossed": true,
          "fee": "0.045082",
          "tid": 195502678643915,
          "feeToken": "USDC",
          "twapId": null
      },
      {
          "coin": "ETH",
          "px": "4410.0",
          "sz": "0.0113",
          "side": "A",
          "time": 1755370620914,
          "startPosition": "0.0113",
          "dir": "Close Long",
          "closedPnl": "-0.0339",
          "hash": "0xcb01958bd88e45bd38780418dacd58011b00d8e9d7e22bce5bd76863160fec92",
          "oid": 37688323761,
          "crossed": true,
          "fee": "0.022424",
          "tid": 329008640192765,
          "feeToken": "USDC",
          "twapId": null
      },
      {
          "coin": "ETH",
          "px": "4413.0",
          "sz": "0.0113",
          "side": "B",
          "time": 1755370544160,
          "startPosition": "0.0",
          "dir": "Open Long",
          "closedPnl": "0.0",
          "hash": "0x03bb408b667f9729999d0418dacb83011a00fb26fffceb4e0519c07872872ae4",
          "oid": 37688311026,
          "crossed": true,
          "fee": "0.02244",
          "tid": 65328027284260,
          "feeToken": "USDC",
          "twapId": null
      },
      {
          "coin": "ETH",
          "px": "4409.9",
          "sz": "0.0453",
          "side": "A",
          "time": 1755369122845,
          "startPosition": "0.0453",
          "dir": "Close Long",
          "closedPnl": "-0.03171",
          "hash": "0xdac62c9cfb23fe6096150418daaa21011500a06490db0e23ce3c9fb77d75d817",
          "oid": 37687960772,
          "crossed": true,
          "fee": "0.089895",
          "tid": 690832171092493,
          "feeToken": "USDC",
          "twapId": null
      }
  ]



{% endtab %}
{% endtabs %}
