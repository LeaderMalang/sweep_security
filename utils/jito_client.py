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
            self.endpoint = endpoint
        else:
            self.endpoint = "https://devnet.block-engine.jito.wtf/api/v1/bundles" if is_devnet else "https://mainnet.block-engine.jito.wtf/api/v1/bundles"
        
        logging.info(f"🚀 Jito Engine: Initialized on {'DEVNET' if is_devnet else 'MAINNET'} endpoint.")

        # Jito Tip Accounts
        if is_devnet:
            self.tip_accounts = [
                "3AVi9Tg9Uo68ayW9F4W9W9W9W9W9W9W9W9W9W9W9W9W", # Generic Devnet Tip
                "DfXoy6AnpY7E6P5w7vC3N8wS1v4tB4zD9ZzGZ2xJpM2w"
            ]
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
        encoded_txs = [base64.b64encode(bytes(tx)).decode("utf-8") for tx in transactions]
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [encoded_txs]
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.endpoint, json=payload)
                result = response.json()
                if "result" in result:
                    logging.info(f"Jito Bundle sent successfully: {result['result']}")
                    return result["result"]
                else:
                    logging.error(f"Jito Bundle failed: {result}")
                    return None
            except Exception as e:
                logging.error(f"Error sending Jito bundle: {e}")
                return None

    def get_random_tip_account(self):
        import random
        return Pubkey.from_string(random.choice(self.tip_accounts))
