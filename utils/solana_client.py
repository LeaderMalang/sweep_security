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
        headers = {"Authorization": f"Bearer {token}"} if token else None
        
        if token:
            logging.info("🔑 ATN Auth: JWT injected into RPC clients.")
            
        self.clients = [AsyncClient(e, headers=headers) for e in self.endpoints]
        self.current_index = 0

    def get_client(self) -> AsyncClient:
        return self.clients[self.current_index]

    async def rotate_endpoint(self):
        self.current_index = (self.current_index + 1) % len(self.clients)
        logging.warning(f"Rotating to RPC endpoint: {self.endpoints[self.current_index]}")

class SolanaClient:
    def __init__(self):
        self.pool = SolanaConnectionPool()
        self.wss_url = config.SOLANA_WSS_URL

    @property
    def client(self):
        return self.pool.get_client()

    async def get_balance(self, address: str):
        pubkey = Pubkey.from_string(address)
        try:
            response = await self.client.get_balance(pubkey)
            return response.value / 1e9
        except Exception as e:
            logging.error(f"RPC Error: {e}")
            await self.pool.rotate_endpoint()
            return await self.get_balance(address)

    async def close(self):
        for client in self.pool.clients:
            await client.close()
