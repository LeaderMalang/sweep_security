import asyncio
import json
import websockets
import config
import logging
from utils.solana_client import SolanaClient
from utils.signature_registry import SignatureRegistry

class WalletMonitor:
    def __init__(self, threat_detector, notification_service, db=None, emergency_service=None):
        self.threat_detector = threat_detector
        self.notification_service = notification_service
        self.solana_client = SolanaClient()
        self.monitored_wallets = config.MONITORED_WALLETS
        self.db = db
        self.emergency_service = emergency_service
        self.retry_delay = 1 

    async def monitor(self):
        """Main loop for monitoring wallets with exponential backoff."""
        while True:
            try:
                await self._run_monitor()
                self.retry_delay = 1 
            except (websockets.exceptions.ConnectionClosed, Exception) as e:
                logging.error(f"Monitor connection lost: {e}. Retrying in {self.retry_delay}s...")
                await asyncio.sleep(self.retry_delay)
                self.retry_delay = min(self.retry_delay * 2, 60) 

    async def _run_monitor(self):
        await self.threat_detector.sync_blacklist()
        
        # 1. Fetch all wallets for all users
        all_users = await self.db.get_all_user_states()
        self.wallet_to_user = {}
        all_wallets = []
        
        for user_row in all_users:
            user = dict(user_row)
            u_wallets = json.loads(user.get('monitored_wallets_json', '[]'))
            for w in u_wallets:
                self.wallet_to_user[w] = str(user['user_id'])
                all_wallets.append(w)

        from utils.atn_auth import get_atn_jwt
        token = get_atn_jwt()
        headers = {
            "Authorization": f"Bearer {token}" if token else "",
            "Referer": "https://troydex.io"
        }

        async with websockets.connect(config.SOLANA_WSS_URL, extra_headers=headers) as websocket:
            for wallet in all_wallets:
                subscribe_msg = {
                    "jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                    "params": [{"mentions": [wallet]}, {"commitment": "confirmed"}]
                }
                await websocket.send(json.dumps(subscribe_msg))
                logging.info(f"Subscribed to logs for {wallet} (User: {self.wallet_to_user[wallet]})")

            while True:
                response = await websocket.recv()
                data = json.loads(response)
                if "params" in data:
                    # We need to find which wallet triggered this
                    # Simplified for now: just log the event
                    logs = data["params"]["result"]["value"]["logs"]
                    # We would typically parse 'mentions' or use subscription IDs to map back
                    # For this implementation, we'll use a placeholder logic to find the wallet
                    # (In production, use separate subscription IDs)
                    await self.handle_notification(data["params"]["result"])

    async def handle_notification(self, result):
        signature = result.get("value", {}).get("signature")
        logs = result.get("value", {}).get("logs", [])
        
        # Simplified: identify the wallet from the logs or meta
        # (In a real implementation, you'd match subscription IDs)
        # For demo, we'll assume we know the target_wallet
        target_wallet = "SomeMonitoredWallet" 
        
        if signature and SignatureRegistry().is_whitelisted(signature):
            logging.info(f"✅ Friendly Fire Prevented: Ignoring own transaction {signature[:10]}...")
            return

        if any("Transfer" in log for log in logs):
            await self.simulate_and_analyze(signature, target_wallet)

    async def simulate_and_analyze(self, signature, wallet_address):
        """Simulates the transaction behavior using the user's specific RPC."""
        user_id = self.wallet_to_user.get(wallet_address)
        if not user_id: return

        logging.info(f"🔍 Analyzing transaction for User {user_id}: {signature}")
        
        # Pass user_id to SolanaClient for dynamic RPC analysis
        # (Assuming analyze_transaction is updated or we use sc here)
        sc = SolanaClient(db=self.db)
        # bal = await sc.get_balance(wallet_address, user_id=user_id)

    async def simulate_and_analyze(self, signature, wallet_address):
        """Simulates the transaction behavior and executes defense if necessary."""
        logging.info(f"🔍 Analyzing transaction: {signature}")
        
        # Heuristic extraction (mocked for demo, would be real RPC call)
        mock_tx_data = {
            "amount": 0.0005,
            "sender": "UnknownAttacker",
            "token_name": "SCAM Airdrop",
            "simulated_impact": "Potential Drain"
        }
        
        score, reasons = self.threat_detector.analyze_transaction(mock_tx_data)
        
        if self.db:
            await self.db.log_threat(wallet_address, score, reasons, signature)

        if score >= config.RISK_SCORE_THRESHOLD:
            await self.notification_service.send_threat_alert(
                wallet_address=wallet_address,
                score=score,
                reasons=reasons,
                tx_hash=signature
            )
            
            # Check for Auto-Defense status in DB
            user_state = await self.db.get_user_state(config.TELEGRAM_CHAT_ID)
            auto_defense = user_state[1] if user_state else False # Placeholder for correct column

            if score >= 90 and auto_defense and self.emergency_service:
                await self.notification_service.send_status_update("🔥 *CRITICAL THREAT: AUTO-DEFENSE TRIGGERED*")
                # In production, we'd use the pre-signed service here for zero latency
                await self.emergency_service.sweep_all(wallet_address, config.SAFE_WALLET_ADDRESS)
