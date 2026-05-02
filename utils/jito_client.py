import httpx
import base64
import logging
from solders.pubkey import Pubkey
from solders.transaction import Transaction

class JitoClient:
    def __init__(self, endpoint=None):
        import config
        is_devnet = any("devnet" in url for url in config.SOLANA_RPC_URLS)
        
        if endpoint:
            self.endpoints = [endpoint]
        else:
            if is_devnet:
                self.endpoints = ["https://devnet.block-engine.jito.wtf/api/v1/bundles"]
            else:
                self.endpoints = [
                    "https://mainnet.block-engine.jito.wtf/api/v1/bundles",
                    "https://ny.mainnet.block-engine.jito.wtf/api/v1/bundles",
                    "https://amsterdam.mainnet.block-engine.jito.wtf/api/v1/bundles",
                    "https://tokyo.mainnet.block-engine.jito.wtf/api/v1/bundles",
                    "https://frankfurt.mainnet.block-engine.jito.wtf/api/v1/bundles"
                ]
        
        logging.info(f"🚀 Jito Engine: Initialized with {len(self.endpoints)} endpoints ({'DEVNET' if is_devnet else 'MAINNET'}).")

        # Jito Tip Accounts
        if is_devnet:
            self.tip_accounts = [
                "3AVi9Tg9Uo68ayW9F4W9W9W9W9W9W9W9W9W9W9W9W9W",
                "DfXoy6AnpY7E6P5w7vC3N8wS1v4tB4zD9ZzGZ2xJpM2w"
            ]
        else:
            self.tip_accounts = [
                "96g9sAg9u3mBsJqcPRrG9q3hc95vX28M7a9ZSRU6YvS5",
                "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
                "Cw8CFyMvAxE3QQexQK9V6NUnatGkQ4b2qAn12pP79L8y",
                "ADu64wAK2mUvC9Yp9r8n6vHNEshNE8Qd9wE4VByxG7p9",
                "DfXoy6AnpY7E6P5w7vC3N8wS1v4tB4zD9ZzGZ2xJpM2w",
                "AD2yRjsSRE83F3Y6G2S9YyT6Y8xNpjC9R2Sj2n6n4S9u",
                "DttwaU9XG8z26f5hFB1Sms9YwB9ZzGZ2xJpM2wD9ZzGZ",
                "3AVi9Tg9Uo68ayW9F4W9W9W9W9W9W9W9W9W9W9W9W9W"
            ]

    async def send_bundle(self, transactions: list):
        """
        Sends a list of signed transactions as a Jito bundle.
        """
        # Convert transactions to base64
        encoded_txs = []
        for tx in transactions:
            raw_tx = bytes(tx) if hasattr(tx, "__bytes__") else tx
            encoded_txs.append(base64.b64encode(raw_tx).decode("utf-8"))
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [encoded_txs, {"encoding": "base64"}]
        }

        async with httpx.AsyncClient() as client:
            for endpoint in self.endpoints:
                try:
                    response = await client.post(endpoint, json=payload, timeout=5.0)
                    result = response.json()
                    if "result" in result:
                        logging.info(f"🚀 Jito Bundle sent via {endpoint}: {result['result']}")
                        return result["result"]
                    elif "error" in result:
                        err = result["error"]
                        if err.get("code") == -32097: # Rate limit
                            logging.warning(f"⚠️ Jito {endpoint} rate limited. Trying next...")
                            continue
                        logging.error(f"❌ Jito {endpoint} error: {err}")
                except Exception as e:
                    logging.error(f"Error sending to Jito {endpoint}: {e}")
            
            return None

    def get_random_tip_account(self):
        import random
        return Pubkey.from_string(random.choice(self.tip_accounts))
