import logging
import asyncio
import json
import websockets
import config
from datetime import datetime

class HoneyPotManager:
    def __init__(self, db, threat_detector, emergency_service=None):
        self.db = db
        self.threat_detector = threat_detector
        self.emergency_service = emergency_service
        self.solana_client = emergency_service.solana_client if emergency_service else None
        self.last_harvests = {} # user_id -> date_string

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
                        
                        # Get all monitored and bait wallets
                        monitored = json.loads(user.get('monitored_wallets_json', '[]') or '[]')
                        baits = json.loads(user.get('bait_wallets_json', '[]') or '[]')
                        all_fleet = list(set(monitored + baits))
                        
                        for wallet in all_fleet:
                            encrypted_key = await self.db.get_vault_key(wallet)
                            if encrypted_key and self.emergency_service:
                                from utils.encryption_utils import EncryptionManager
                                encryptor = EncryptionManager(config.ENCRYPTION_KEY)
                                privkey = encryptor.decrypt(encrypted_key)
                                # Total harvest to safe wallet
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
                # 1. Fetch all users
                all_users = await self.db.get_all_user_states()
                
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
                        # In production, this would use a volatility index
                        threshold *= 0.8
                        logging.info(f"🧠 SMART MODE: Threshold lowered to {threshold} for User {user_id}")

                    retain = user['skimming_retain']
                    bait_wallets = json.loads(user.get('bait_wallets_json', '[]'))
                    
                    if not bait_wallets: continue

                    for wallet in bait_wallets:
                        # Get balance using user's specific RPC
                        balance = await self.solana_client.get_balance(wallet, user_id=user_id)
                        
                        if balance >= threshold:
                            logging.warning(f"🍯 HARVEST DETECTED for User {user_id}: {wallet} balance ({balance}) hits threshold ({threshold})")
                            
                            encrypted_key = await self.db.get_vault_key(wallet)
                            if encrypted_key and self.emergency_service:
                                from utils.encryption_utils import EncryptionManager
                                encryptor = EncryptionManager(config.ENCRYPTION_KEY)
                                privkey = encryptor.decrypt(encrypted_key)
                                
                                # Execute harvest using Jito and the user's RPC
                                await self.emergency_service.sweep_all_sol_jito(privkey, user_id=user_id)
                
                await asyncio.sleep(60) # Check every minute
            except Exception as e:
                logging.error(f"Skimmer Loop Error: {e}")
                await asyncio.sleep(10)

    async def start_monitoring(self):
        """Monitors all users' bait and monitored wallets for activity."""
        logging.info("🔭 Sentinel-Zero: Dynamic Watchtower Active.")
        
        from utils.atn_auth import get_atn_jwt
        token = get_atn_jwt()
        headers = {
            "Authorization": f"Bearer {token}" if token else "",
            "Referer": "https://troydex.io"
        }
        
        async with websockets.connect(config.SOLANA_WSS_URL, extra_headers=headers) as websocket:
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

            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)
                    if "params" in data:
                        await self.handle_security_event(data["params"]["result"], all_wallets)
                except Exception as e:
                    logging.error(f"Sentinel Loop error: {e}")
                    await asyncio.sleep(5)

    async def handle_security_event(self, result, monitored_list):
        """Identifies the victim and triggers an immediate counter-sweep."""
        logs = result.get('value', {}).get('logs', [])
        # Simple heuristic: If we see a transfer in the logs, check if it targets our fleet
        signature = result.get('value', {}).get('signature')
        
        logging.warning(f"🎯 THREAT DETECTED: Activity on Monitored Fleet! Sig: {signature}")
        
        # Trigger Global Panic for all users associated with this activity
        # (Optimized: In production, we'd map the specific wallet to the user_id)
        users = await self.db.get_all_user_states()
        for u in users:
            user = dict(u)
            user_id = str(user['user_id'])
            if user.get('auto_defense'):
                await self.emergency_service.execute_all(user_id, self.db)

    async def broadcast_threat(self, address):
        """Simulates broadcasting threat intelligence to a central network."""
        logging.info(f"📡 Broadcasting threat intel for {address} to Community Network...")
        # In Phase 3, this would be an API call to a shared threat DB
        await asyncio.sleep(1)
