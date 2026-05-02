import asyncio
import logging
import config
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from utils.atn_auth import get_atn_jwt

def get_atn_headers(url: str = ""):
    token = get_atn_jwt()
    headers = {"Referer": "https://troydex.io"}
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
        self._custom_clients: dict = {}  # url -> AsyncClient (cached to avoid per-call leaks)

    @property
    def client(self):
        return self.pool.get_client()

    async def get_client_for_user(self, user_id: str):
        """Returns a custom AsyncClient if the user has one, otherwise the pool client.
        Custom RPC clients are cached per URL to avoid creating a new connection on every call."""
        if self.db:
            row = await self.db.get_user_state(user_id)
            if not row: return self.client
            state = dict(row)

            # 1. Check for Custom RPC first (bypass usage tracking)
            if state.get('custom_rpc_url'):
                url = state['custom_rpc_url']
                if url not in self._custom_clients:
                    self._custom_clients[url] = AsyncClient(url, extra_headers=get_atn_headers(url))
                return self._custom_clients[url]

            # Track RPC usage for users on our system RPC
            await self.db.increment_rpc_usage(user_id)

            # 2. System RPC (Pro/Lite/Admin)
            tier = state.get('subscription_tier', 'free').lower()
            is_admin = user_id == str(config.TELEGRAM_CHAT_ID)

            if is_admin or tier in ['lite', 'pro', 'premium']:
                return self.client

        # 3. Free Tier Fallback
        url = config.SOLANA_RPC_URLS[0]
        if url not in self._custom_clients:
            self._custom_clients[url] = AsyncClient(url, extra_headers=get_atn_headers(url))
        return self._custom_clients[url]

    async def get_balance(self, address: str, user_id: str = None, retries: int = 3) -> float:
        """Gets balance for an address with retry/backoff logic."""
        client = await self.get_client_for_user(user_id) if user_id else self.client
        try:
            pub = Pubkey.from_string(str(address))
            response = await client.get_balance(pub)
            return response.value / 1e9
        except Exception as e:
            if retries <= 0:
                logging.error(f"❌ RPC Final Failure (Balance): {e}")
                return 0.0
            wait_time = (4 - retries) * 1.5 
            logging.warning(f"RPC Balance Error ({retries} retries left): {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
            await self.pool.rotate_endpoint()
            return await self.get_balance(address, user_id, retries - 1)

    async def get_latest_blockhash(self, user_id: str = None, retries: int = 3):
        """Gets latest blockhash with retry/backoff logic."""
        client = await self.get_client_for_user(user_id) if user_id else self.client
        try:
            response = await client.get_latest_blockhash()
            return response.value.blockhash
        except Exception as e:
            if retries <= 0:
                logging.error(f"❌ RPC Final Failure (Blockhash): {e}")
                return None
            wait_time = (4 - retries) * 1.5 
            logging.warning(f"RPC Blockhash Error ({retries} retries left): {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
            await self.pool.rotate_endpoint()
            return await self.get_latest_blockhash(user_id, retries - 1)

    async def get_account_info(self, address: str, user_id: str = None, retries: int = 3):
        """Gets account info with retry/backoff logic."""
        client = await self.get_client_for_user(user_id) if user_id else self.client
        try:
            pub = Pubkey.from_string(str(address))
            response = await client.get_account_info(pub)
            return response.value
        except Exception as e:
            if retries <= 0:
                logging.error(f"❌ RPC Final Failure (AccountInfo): {e}")
                return None
            wait_time = (4 - retries) * 1.5 
            logging.warning(f"RPC AccountInfo Error ({retries} retries left): {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
            await self.pool.rotate_endpoint()
            return await self.get_account_info(address, user_id, retries - 1)

    async def send_raw_transaction(self, tx_bytes: bytes, user_id: str = None, retries: int = 3):
        """Sends raw transaction with retry/backoff logic."""
        client = await self.get_client_for_user(user_id) if user_id else self.client
        try:
            response = await client.send_raw_transaction(tx_bytes)
            return str(response.value)
        except Exception as e:
            if retries <= 0:
                logging.error(f"❌ RPC Final Failure (SendTX): {e}")
                return None
            wait_time = (4 - retries) * 1.5 
            logging.warning(f"RPC SendTX Error ({retries} retries left): {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
            await self.pool.rotate_endpoint()
            return await self.send_raw_transaction(tx_bytes, user_id, retries - 1)

    async def get_priority_fee_estimate(self, user_id: str = None, retries: int = 2):
        """Fetches dynamic priority fee using the standard getRecentPrioritizationFees RPC method.
        Works on all RPC providers (Helius, QuickNode, Alchemy, public mainnet-beta).
        Returns an estimated Jito tip in SOL, or None on failure."""
        client = await self.get_client_for_user(user_id) if user_id else self.client
        try:
            import httpx
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getRecentPrioritizationFees",
                "params": []
            }
            url = str(client._provider.endpoint_uri)
            async with httpx.AsyncClient() as http_client:
                res = await http_client.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5.0
                )
                data = res.json()
                if "result" in data and isinstance(data["result"], list) and data["result"]:
                    # Each entry: {"slot": N, "prioritizationFee": M} where M is µlamports/CU
                    fees = [e["prioritizationFee"] for e in data["result"] if e.get("prioritizationFee", 0) > 0]
                    if fees:
                        fees.sort()
                        # Use the 75th-percentile fee as the network congestion signal
                        p75_microlamports_per_cu = fees[int(len(fees) * 0.75)]
                        # Scale to a Jito tip in SOL:
                        # typical transfer = ~200 CU; µlamps/CU → lamports → SOL
                        # multiply by 1.5x safety buffer, cap between 0.0001 and 0.05 SOL
                        estimated_sol = p75_microlamports_per_cu * 200 / 1e6 / 1e9
                        return max(0.0001, min(estimated_sol * 1.5, 0.05))
        except Exception as e:
            if retries <= 0:
                logging.error(f"❌ RPC Priority Fee Error: {e}")
                return None
            await asyncio.sleep((3 - retries) * 1.0)
            await self.pool.rotate_endpoint()
            return await self.get_priority_fee_estimate(user_id, retries - 1)
        return None

    async def close(self):
        for client in self.pool.clients:
            await client.close()
        for client in self._custom_clients.values():
            await client.close()
        self._custom_clients.clear()
