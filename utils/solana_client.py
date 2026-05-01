import asyncio
import logging
import config
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from utils.atn_auth import get_atn_jwt

def get_atn_headers(url: str = ""):
    headers = {"Referer": "https://troydex.io"}
    # Only send JWT if it's not a permanent API key link (hex at the end)
    # Permanent links usually don't want the Bearer token or it conflicts
    if "/json_rpc/" not in url:
        token = get_atn_jwt()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return headers

class SolanaConnectionPool:
    def __init__(self):
        self.endpoints = config.SOLANA_RPC_URLS
        
        # Initialize pool of clients with fresh headers
        self.clients = [AsyncClient(e, extra_headers=get_atn_headers(e)) for e in self.endpoints]
        self.current_index = 0
        self.last_auth_time = asyncio.get_event_loop().time()

    def get_client(self) -> AsyncClient:
        # Refresh pool if headers are older than 45 mins (ATN tokens expire)
        try:
            loop = asyncio.get_event_loop()
            now = loop.time()
            if now - self.last_auth_time > 2700: 
                 self.clients = [AsyncClient(e, extra_headers=get_atn_headers(e)) for e in self.endpoints]
                 self.last_auth_time = now
                 logging.info("♻️ RPC Pool: Headers refreshed.")
        except Exception as e:
            logging.error(f"Failed to refresh RPC pool: {e}")
            
        return self.clients[self.current_index]

    async def rotate_endpoint(self):
        if len(self.clients) <= 1:
            return
        self.current_index = (self.current_index + 1) % len(self.clients)
        logging.warning(f"Rotating to RPC endpoint: {self.endpoints[self.current_index]}")

class SolanaClient:
    def __init__(self, db=None):
        self.pool = SolanaConnectionPool()
        self.wss_url = config.SOLANA_WSS_URL
        self.db = db

    @property
    def client(self):
        return self.pool.get_client()

    async def get_client_for_user(self, user_id: str):
        """Returns a custom AsyncClient if the user has one, otherwise the pool client."""
        if self.db:
            row = await self.db.get_user_state(user_id)
            if not row: return self.client
            state = dict(row)

            # 1. Check for Custom RPC first (By-pass usage tracking)
            if state.get('custom_rpc_url'):
                url = state['custom_rpc_url']
                return AsyncClient(url, extra_headers=get_atn_headers(url))

            # 2. Using System RPC (Pro/Lite/Admin)
            tier = state.get('subscription_tier', 'free').lower()
            is_admin = user_id == str(config.TELEGRAM_CHAT_ID)
            
            if is_admin or tier in ['lite', 'pro', 'premium']:
                await self.db.increment_rpc_usage(user_id)
                return self.client
        
        # 3. Free Tier Fallback (Use first configured RPC - respects .env)
        return AsyncClient(config.SOLANA_RPC_URLS[0])

    async def get_balance(self, address: str, user_id: str = None, retries=3):
        if retries < 0:
            return 0.0
        pubkey = Pubkey.from_string(address)
        
        # Use custom client if user_id provided
        target_client = await self.get_client_for_user(user_id) if user_id else self.client
        
        try:
            response = await target_client.get_balance(pubkey)
            # If we created a temp client, we should close it (simplified here)
            return response.value / 1e9
        except Exception as e:
            error_details = ""
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_details = e.response.text
            
            if retries <= 0:
                logging.error(f"❌ RPC Final Failure: {e} | Details: {error_details}")
                return 0.0
            
            logging.error(f"RPC Error ({retries} retries left): {e} | Details: {error_details}")
            await self.pool.rotate_endpoint()
            return await self.get_balance(address, user_id, retries - 1)

    async def close(self):
        for client in self.pool.clients:
            await client.close()
