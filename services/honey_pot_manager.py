import logging
import asyncio
import json
import websockets
import config
from datetime import datetime
from utils.solana_client import SolanaClient
from utils.signature_registry import SignatureRegistry

class HoneyPotManager:
    def __init__(self, db, threat_detector, emergency_service=None):
        self.db = db
        self.threat_detector = threat_detector
        self.emergency_service = emergency_service
        self.solana_client = emergency_service.solana_client if emergency_service else None
        self.last_harvests = {} # user_id -> date_string
        self.active_websocket = None

    async def run_daily_harvest(self):
        """Executes a total harvest for all users once per day at their configured time."""
        logging.info("🕰️ Chronos Engine: Active and Scheduling Daily Harvests...")
        while True:
            try:
                now = datetime.now()
                now_str = now.strftime("%H:%M")
                today_str = now.strftime("%Y-%m-%d")
                
                users = await self.db.get_all_user_states()
                for user_row in users:
                    user = dict(user_row)
                    user_id = str(user['user_id'])
                    
                    if not user.get('daily_sweep_enabled'):
                        continue
                    
                    # Check if it's the right time and we haven't harvested today
                    if user.get('daily_sweep_time') == now_str and self.last_harvests.get(user_id) != today_str:
                        logging.warning(f"🕰️ CHRONOS TRIGGER: Starting scheduled harvest for User {user_id}")
                        self.last_harvests[user_id] = today_str
                        
                        # Get ONLY bait wallets for daily harvest — never sweep monitored/protected wallets
                        baits = json.loads(user.get('bait_wallets_json', '[]') or '[]')
                        safe_addr = (user.get('safe_wallet_address') or '').strip()
                        all_fleet = [w.strip() for w in baits if w.strip() and w.strip() != safe_addr]
                        
                        for wallet in all_fleet:
                            privkey = await self.emergency_service._decrypt_wallet_key(wallet)
                            if privkey and self.emergency_service:
                                await self.emergency_service.sweep_all_sol_jito(privkey, user_id=user_id)
                
                await asyncio.sleep(30) # Check twice per minute for precision
            except Exception as e:
                logging.error(f"Chronos Engine Error: {e}")
                await asyncio.sleep(10)

    async def run_skimmer(self):
        """Background loop to skim excess funds from all users' bait wallets."""
        logging.info("🍯 Skimmer Engine: Active and Monitoring all users...")
        while True:
            try:
                users = await self.db.get_all_user_states()
                for user_row in users:
                    user = dict(user_row)
                    if not user['skimming_enabled']:
                        continue

                    user_id = str(user['user_id'])
                    threshold = user['skimming_threshold']
                    
                    # 2. Smart Threshold Adjustment (Advanced Feature)
                    if user.get('smart_thresholds_enabled'):
                        # If enabled, lower threshold by 20% during 'simulated' high activity
                        threshold *= 0.8
                    
                    # Ensure threshold is sane (min 0.001 SOL)
                    threshold = max(threshold, 0.001)
                    logging.info(f"🧠 SMART MODE: Active threshold {threshold} for User {user_id}")

                    retain = user['skimming_retain']
                    bait_wallets = json.loads(user.get('bait_wallets_json', '[]') or '[]')
                    # CRITICAL: Only harvest bait wallets — never touch monitored (protected) wallets
                    safe_addr = (user.get('safe_wallet_address') or '').strip()
                    all_harvest_wallets = [w.strip() for w in bait_wallets if w.strip() and w.strip() != safe_addr]

                    if not all_harvest_wallets:
                        logging.info(f"No bait wallets to skim for User {user_id}. Skipping.")
                        continue

                    for wallet in all_harvest_wallets:
                        # Get balance using user's specific RPC
                        balance = await self.solana_client.get_balance(wallet, user_id=user_id)
                        
                        if balance >= (threshold + 0.01) and balance > 0:
                            logging.warning(f"🍯 HARVEST DETECTED for User {user_id}: {wallet} balance ({balance}) hits threshold ({threshold})")
                            
                            privkey = await self.emergency_service._decrypt_wallet_key(wallet)
                            if privkey and self.emergency_service:
                                await self.emergency_service.sweep_all_sol_jito(privkey, user_id=user_id, retain_sol=retain)
                
                await asyncio.sleep(60) # Check every minute
            except Exception as e:
                logging.error(f"Skimmer Loop Error: {e}")
                await asyncio.sleep(10)

    async def start_monitoring(self):
        """Main loop for the Sentinel-Zero watchtower with reconnection logic."""
        logging.info("🔭 Sentinel-Zero: Dynamic Watchtower Active.")
        retry_delay = 1
        while True:
            try:
                await self._run_sentinel_session()
                retry_delay = 1 # Reset on success
            except Exception as e:
                logging.error(f"Sentinel Connection lost: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60) # Exponential backoff

    async def _run_sentinel_session(self):
        """Internal logic for a single WebSocket session."""
        from utils.solana_client import get_atn_headers
        headers = get_atn_headers(config.SOLANA_WSS_URL)
        
        async with websockets.connect(config.SOLANA_WSS_URL, extra_headers=headers) as websocket:
            self.active_websocket = websocket
            # 1. Subscribe to all relevant wallets
            users = await self.db.get_all_user_states()
            all_wallets = set()
            for u in users:
                user = dict(u)
                baits = json.loads(user.get('bait_wallets_json', '[]') or '[]')
                monitored = json.loads(user.get('monitored_wallets_json', '[]') or '[]')
                all_wallets.update(baits)
                all_wallets.update(monitored)

            if not all_wallets:
                logging.warning("No wallets to monitor. Waiting...")
                await asyncio.sleep(60)
                return

            for wallet in all_wallets:
                subscribe_msg = {
                    "jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                    "params": [{"mentions": [wallet]}, {"commitment": "confirmed"}]
                }
                await websocket.send(json.dumps(subscribe_msg))
                logging.info(f"🔭 Watchtower Subscribed: {wallet}")

            while True:
                response = await websocket.recv()
                data = json.loads(response)
                if "params" in data:
                    await self.handle_security_event(data["params"]["result"], all_wallets)

    async def trigger_reconnect(self):
        """Forces the watchtower to reconnect and refresh its wallet subscription list."""
        if self.active_websocket:
            logging.info("🔄 Watchtower: Dynamic reconnect triggered (Subscription list updated).")
            await self.active_websocket.close()
            self.active_websocket = None

    async def handle_security_event(self, result, monitored_list):
        """Identifies the victim and triggers an immediate counter-sweep."""
        signature = result.get('value', {}).get('signature')
        
        # 0. Fast Signature Whitelist
        if signature and SignatureRegistry().is_whitelisted(signature):
            logging.info(f"✅ Friendly Fire Prevented: Ignoring own transaction {signature[:10]}...")
            return
            
        logs = result.get('value', {}).get('logs', [])
        logging.info(f"🔍 Analyzing transaction: {signature}")
        
        sender = None
        # 0.5 Deep Sender Check (Fetch transaction to see who sent it)
        try:
            tx_info = await self.solana_client.client.get_transaction(
                signature, 
                max_supported_transaction_version=0
            )
            if tx_info and tx_info.value:
                keys = tx_info.value.transaction.transaction.message.account_keys
                sender = str(keys[0])
                
                if sender == config.SAFE_WALLET_ADDRESS:
                    logging.info(f"✅ Friendly Fire Prevented: Transaction from GLOBAL SAFE WALLET.")
                    return
        except Exception as e:
            logging.error(f"Error fetching tx info for whitelist check: {e}")

        # Trigger Global Panic for all users associated with this activity
        users = await self.db.get_all_user_states()
        for u in users:
            user = dict(u)
            user_id = str(user['user_id'])
            user_safe = user.get('safe_wallet_address')
            
            if sender and user_safe and sender == user_safe:
                logging.info(f"✅ Friendly Fire Prevented: Transaction from User {user_id}'s SAFE WALLET.")
                continue

            if user.get('auto_defense'):
                # 1. Send Immediate Alert
                from services.notification_service import NotificationService
                ns = self.emergency_service.notification_service if hasattr(self.emergency_service, 'notification_service') else None
                if ns:
                    await ns.send_threat_alert(
                        wallet_address="Monitored Fleet",
                        score=100,
                        reasons=["🚨 UNAUTHORIZED TRANSFER DETECTED"],
                        tx_hash=signature,
                        user_id=user_id
                    )
                
                # 2. Trigger Global Rescue
                await self.emergency_service.execute_all(user_id)

    async def broadcast_threat(self, address):
        """Simulates broadcasting threat intelligence to a central network."""
        logging.info(f"📡 Broadcasting threat intel for {address} to Community Network...")
        # In Phase 3, this would be an API call to a shared threat DB
        await asyncio.sleep(1)
