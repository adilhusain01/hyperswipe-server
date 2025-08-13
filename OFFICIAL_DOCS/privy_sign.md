# eth_sendTransaction

> Sign and send a transaction using the eth_sendTransaction method.

<RequestExample>
  ```sh cURL
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "eth_sendTransaction",
    "caip2": "eip155:11155111",
    "chain_type": "ethereum",
    "sponsor": true,
    "params": {
      "transaction": {
        "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "value": "0x2386F26FC10000",
      }
    }
  }'
  ```
</RequestExample>

<ResponseExample>
  ```json 200
  {
    "method": "eth_sendTransaction",
    "data": {
      "hash": "0xfc3a736ab2e34e13be2b0b11b39dbc0232a2e755a11aa5a9219890d3b2c6c7d8",
      "caip2": "eip155:11155111",
      "transaction_id": "y90vpg3bnkjxhw541c2zc6a9"
    }
  }
  ```
</ResponseExample>

<Warning>
  A successful response indicates that the transaction has been broadcasted to the network.
  Transactions may get broadcasted but still fail to be confirmed by the network. To handle these
  scenarios, see our guide on [speeding up transactions](/recipes/speeding-up-transactions).
</Warning>

### Headers

<ParamField header="privy-app-id" type="string" required>
  ID of your Privy app.
</ParamField>

<ParamField header="privy-authorization-signature" type="string">
  Request authorization signature. If multiple signatures are required, they should be comma
  separated.
</ParamField>

### Path Parameters

<ParamField path="wallet_id" type="string" required>
  ID of the wallet to get.
</ParamField>

### Body

<ParamField body="method" type="string" defaultValue="eth_sendTransaction" required>
  Available options: `eth_sendTransaction`
</ParamField>

<ParamField body="caip2" type="string" initialValue="eip155:11155111" required />

<ParamField body="sponsor" type="boolean">
  Optional parameter to enable gas sponsorship for this transaction. Your app must be configured
  with the "conditional" gas sponsorship strategy.
</ParamField>

<ParamField body="params" type="object" required>
  <Expandable title="child attributes" defaultOpen="true">
    <ParamField body="transaction" type="object" required>
      <Expandable title="child attributes" defaultOpen="true">
        <ParamField body="from" type="string" />

        <ParamField body="to" type="string" />

        <ParamField body="chain_id" type="string" />

        <ParamField body="nonce" type="string" />

        <ParamField body="data" type="string" />

        <ParamField body="value" type="string">
          The value to send in the transaction in wei as a hexadecimal string.
        </ParamField>

        <ParamField body="type" type="number">
          Available options: `0`, `1`, `2`
        </ParamField>

        <ParamField body="gas_limit" type="string" />

        <ParamField body="gas_price" type="string" />
      </Expandable>
    </ParamField>
  </Expandable>
</ParamField>

<ParamField body="address" type="string" />

<ParamField body="chain_type" type="string">
  Available options: `ethereum`
</ParamField>

### Returns

<ResponseField name="method" type="enum<string>" required>
  Available options: `eth_sendTransaction`
</ResponseField>

<ResponseField name="data" type="object" required>
  <Expandable title="child attributes" defaultOpen="true">
    <ResponseField name="hash" type="string" required />

    <ResponseField name="caip2" type="string" required />

    <ResponseField name="transaction_id" type="string" />
  </Expandable>
</ResponseField>



# personal_sign

> Sign a message using the personal_sign method.

<RequestExample>
  ```sh cURL
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "personal_sign",
    "params": {
      "message": "Hello from Privy!",
      "encoding": "utf-8"
    }
  }'
  ```
</RequestExample>

<ResponseExample>
  ```json 200
  {
    "method": "personal_sign",
    "data": {
      "signature": "0x0db9c7bd881045cbba28c347de6cc32a653e15d7f6f2f1cec21d645f402a64196e877eb45d3041f8d2ab1a76f57f408b63894cfc6f339d8f584bd26efceae3081c",
      "encoding": "hex"
    }
  }
  ```
</ResponseExample>

### Headers

<ParamField header="privy-app-id" type="string" required>
  ID of your Privy app.
</ParamField>

<ParamField header="privy-authorization-signature" type="string">
  Request authorization signature. If multiple signatures are required, they should be comma
  separated.
</ParamField>

### Path Parameters

<ParamField path="wallet_id" type="string" required>
  ID of the wallet to get.
</ParamField>

### Body

<ParamField body="method" type="string" defaultValue="personal_sign" required>
  Available options: `personal_sign`
</ParamField>

<ParamField body="params" type="object" required>
  <Expandable title="child properties" defaultOpen="true">
    <ParamField body="message" type="string" />

    <ParamField body="encoding" type="string" initialValue="utf-8">
      Available options: `utf-8`, `hex`
    </ParamField>
  </Expandable>
</ParamField>

### Response

<ResponseField name="method" type="enum<string>" required>
  Available options: `personal_sign`
</ResponseField>

<ResponseField name="data" type="object" required>
  <Expandable title="child properties" defaultOpen="true">
    <ResponseField name="signature" type="string" required />

    <ResponseField name="encoding" type="enum<string>">
      Available options: `utf-8`, `hex`
    </ResponseField>
  </Expandable>
</ResponseField>




# eth_signTransaction

> Sign a transaction using the eth_signTransaction method.

<RequestExample>
  ```sh cURL
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "eth_signTransaction",
    "params": {
      "transaction": {
        "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "value": "0x2386F26FC10000",
        "chain_id": 11155111,
        "data": "0x",
        "gas_limit": 50000,
        "nonce": 0,
        "max_fee_per_gas": 1000308,
        "max_priority_fee_per_gas": "1000000"
      }
    }
  }'
  ```
</RequestExample>

<ResponseExample>
  ```json 200
  {
    "method": "eth_signTransaction",
    "data": {
      "signed_transaction": "0x02f870830138de80830f4240830f437480940b81418147df37155d643b5cb65ba6c8cb7aba76872000000000000480c080a05c11a2166ec56189d993dec477477d962ce0d4c466ab7ed8982110621ec87a57a003c796590c0c62eac30acd412f2aa0e8ad740c4ded86fb64d3326ee4c0ea804c",
      "encoding": "rlp"
    }
  }
  ```
</ResponseExample>

### Headers

<ParamField header="privy-app-id" type="string" required>
  ID of your Privy app.
</ParamField>

<ParamField header="privy-authorization-signature" type="string">
  Request authorization signature. If multiple signatures are required, they should be comma
  separated.
</ParamField>

### Path Parameters

<ParamField path="wallet_id" type="string" required>
  ID of the wallet to get.
</ParamField>

### Body

<ParamField body="method" type="string" defaultValue="eth_signTransaction" required>
  Available options: `eth_signTransaction`
</ParamField>

<ParamField body="params" type="object" required>
  <Expandable title="child attributes" defaultOpen="true">
    <ParamField body="transaction" type="object" required>
      <Expandable title="child attributes" defaultOpen="true">
        <ParamField body="from" type="string" />

        <ParamField body="to" type="string" />

        <ParamField body="chain_id" type="string" />

        <ParamField body="nonce" type="string" />

        <ParamField body="data" type="string" />

        <ParamField body="value" type="string">
          The value to send in the transaction in wei as a hexadecimal string.
        </ParamField>

        <ParamField body="type" type="number">
          Available options: `0`, `1`, `2`
        </ParamField>

        <ParamField body="gas_limit" type="string" />

        <ParamField body="gas_price" type="string" />
      </Expandable>
    </ParamField>
  </Expandable>
</ParamField>

### Response

<ResponseField name="method" type="enum<string>" required>
  Available options: `eth_signTransaction`
</ResponseField>

<ResponseField name="data" type="object" required>
  <Expandable title="child properties" defaultOpen="true">
    <ResponseField name="signed_transaction" type="string" required />

    <ResponseField name="encoding" type="enum<string>">
      Available options: `rlp`
    </ResponseField>
  </Expandable>
</ResponseField>
