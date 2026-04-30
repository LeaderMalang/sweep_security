import asyncio
import logging
import config
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from utils.atn_auth import get_atn_jwt

class SolanaConnectionPool:
    def __init__(self):
        self.endpoints = [config.SOLANA_RPC_URL]
        
        # Get JWT for All That Node if private.pem exists
        token = get_atn_jwt()
        if token:
            logging.info("🔑 ATN Auth: JWT generated successfully.")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Referer": "https://troydex.io"
            }
        else:
            logging.warning("⚠️ ATN Auth: No JWT generated (check private.pem).")
            headers = {"Referer": "https://troydex.io"}
        
        # Use extra_headers keyword for authorization
        self.clients = [AsyncClient(e, extra_headers=headers) for e in self.endpoints]
        self.current_index = 0

    def get_client(self) -> AsyncClient:
        return self.clients[self.current_index]

    async def rotate_endpoint(self):
        if len(self.clients) <= 1:
            return
        self.current_index = (self.current_index + 1) % len(self.clients)
        logging.warning(f"Rotating to RPC endpoint: {self.endpoints[self.current_index]}")

class SolanaClient:
    def __init__(self):
        self.pool = SolanaConnectionPool()
        self.wss_url = config.SOLANA_WSS_URL

    @property
    def client(self):
        return self.pool.get_client()

    async def get_balance(self, address: str, retries=3):
        if retries < 0:
            return 0.0
        pubkey = Pubkey.from_string(address)
        try:
            response = await self.client.get_balance(pubkey)
            return response.value / 1e9
        except Exception as e:
            # Try to extract the error body for debugging JWT issues
            error_details = ""
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_details = e.response.text
            
            if retries <= 0:
                logging.error(f"❌ RPC Final Failure: {e} | Details: {error_details}")
                return 0.0
            
            logging.error(f"RPC Error ({retries} retries left): {e} | Details: {error_details}")
            await self.pool.rotate_endpoint()
            return await self.get_balance(address, retries - 1)

    async def close(self):
        for client in self.pool.clients:
            await client.close()
