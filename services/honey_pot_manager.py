import logging
import asyncio
import json
import websockets
import config

class HoneyPotManager:
    def __init__(self, db, threat_detector, emergency_service=None):
        self.db = db
        self.threat_detector = threat_detector
        self.emergency_service = emergency_service
        self.solana_client = emergency_service.solana_client if emergency_service else None
        # In a real app, these would be separate wallets generated for this purpose
        self.honey_pots = ["BaitWalletAddress1", "BaitWalletAddress2"]

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
                    retain = user['skimming_retain']
                    bait_wallets = json.loads(user.get('bait_wallets_json', '[]'))
                    
                    if not bait_wallets: continue

                    for wallet in bait_wallets:
                        # Get balance using user's specific RPC
                        balance = await self.solana_client.get_balance(wallet, user_id=user_id)
                        
                        if balance >= threshold:
                            skim_amount = balance - retain
                            logging.warning(f"🍯 HARVEST DETECTED for User {user_id}: {wallet} balance ({balance}) exceeds threshold ({threshold})")
                            
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
        """Monitors honey pot addresses for activity."""
        if not self.honey_pots:
            return

        logging.info(f"Starting Honey Pot Network with {len(self.honey_pots)} wallets.")
        from utils.atn_auth import get_atn_jwt
        token = get_atn_jwt()
        headers = {
            "Authorization": f"Bearer {token}" if token else "",
            "Referer": "https://troydex.io"
        }
        # Using a more robust way to pass headers for websockets v13.0+
        async with websockets.connect(config.SOLANA_WSS_URL, extra_headers=headers) as websocket:
            for wallet in self.honey_pots:
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
                        await self.handle_attacker(data["params"]["result"])
                except Exception as e:
                    logging.error(f"Honey Pot loop error: {e}")
                    await asyncio.sleep(5)

    async def handle_attacker(self, result):
        """Blacklists the sender of any transaction to a honey pot."""
        # Simulated extraction of attacker address
        attacker_address = "Attacker_Found_In_HoneyPot"
        
        logging.warning(f"🎯 HONEY POT TRIGGERED! Blacklisting attacker: {attacker_address}")
        
        await self.db.add_to_blacklist(attacker_address, "Honey Pot Interaction")
        await self.threat_detector.sync_blacklist()
        
        # Broadcast to community (simulated)
        await self.broadcast_threat(attacker_address)

    async def broadcast_threat(self, address):
        """Simulates broadcasting threat intelligence to a central network."""
        logging.info(f"📡 Broadcasting threat intel for {address} to Community Network...")
        # In Phase 3, this would be an API call to a shared threat DB
        await asyncio.sleep(1)
