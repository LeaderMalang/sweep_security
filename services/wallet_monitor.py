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
        self.solana_client = SolanaClient(db=db)
        self.monitored_wallets = config.MONITORED_WALLETS
        self.db = db
        self.emergency_service = emergency_service
        self.wallet_to_user: dict = {}
        self.retry_delay = 1

    async def monitor(self):
        """Main loop with exponential backoff reconnection."""
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

        all_users = await self.db.get_all_user_states()
        self.wallet_to_user = {}
        all_wallets = []

        for user_row in all_users:
            user = dict(user_row)
            u_wallets = json.loads(user.get("monitored_wallets_json", "[]"))
            for w in u_wallets:
                self.wallet_to_user[w] = str(user["user_id"])
                all_wallets.append(w)

        if not all_wallets:
            logging.warning("No wallets to monitor. Sleeping 60s...")
            await asyncio.sleep(60)
            return

        from utils.solana_client import get_atn_headers
        headers = get_atn_headers(config.SOLANA_WSS_URL)

        async with websockets.connect(config.SOLANA_WSS_URL, extra_headers=headers) as websocket:
            for wallet in all_wallets:
                subscribe_msg = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "logsSubscribe",
                    "params": [{"mentions": [wallet]}, {"commitment": "confirmed"}],
                }
                await websocket.send(json.dumps(subscribe_msg))
                logging.info(f"Subscribed to logs for {wallet} (User: {self.wallet_to_user[wallet]})")

            while True:
                response = await websocket.recv()
                data = json.loads(response)
                if "params" in data:
                    await self.handle_notification(data["params"]["result"])

    async def handle_notification(self, result):
        signature = result.get("value", {}).get("signature")
        logs = result.get("value", {}).get("logs", [])

        if signature and SignatureRegistry().is_whitelisted(signature):
            logging.info(f"✅ Friendly Fire Prevented: {signature[:12]}...")
            return

        # Map the event back to a monitored wallet by scanning log lines
        target_wallet = None
        for log_line in logs:
            for wallet in self.wallet_to_user:
                if wallet in log_line:
                    target_wallet = wallet
                    break
            if target_wallet:
                break

        if not target_wallet:
            result_str = str(result)
            for wallet in self.wallet_to_user:
                if wallet in result_str:
                    target_wallet = wallet
                    break

        if not target_wallet:
            logging.debug("Could not identify target wallet from event. Skipping.")
            return

        if any("Transfer" in log for log in logs):
            await self.simulate_and_analyze(signature, target_wallet)

    async def simulate_and_analyze(self, signature: str, wallet_address: str):
        """Fetches real transaction data from the RPC and runs threat analysis."""
        user_id = self.wallet_to_user.get(wallet_address)
        if not user_id:
            return

        logging.info(f"🔍 Analyzing tx {signature[:12]}... wallet {wallet_address[:8]}...")

        tx_data = {
            "amount": 0.0,
            "sender": "Unknown",
            "token_name": "",
            "network": "solana",
        }

        try:
            client = await self.solana_client.get_client_for_user(user_id)
            tx_info = await client.get_transaction(
                signature, max_supported_transaction_version=0
            )
            if tx_info and tx_info.value:
                msg = tx_info.value.transaction.transaction.message
                keys = [str(k) for k in msg.account_keys]
                if keys:
                    tx_data["sender"] = keys[0]

                meta = tx_info.value.transaction.meta
                if meta and meta.pre_balances and meta.post_balances and wallet_address in keys:
                    idx = keys.index(wallet_address)
                    if idx < len(meta.pre_balances):
                        delta = meta.pre_balances[idx] - meta.post_balances[idx]
                        tx_data["amount"] = abs(delta) / 1e9
        except Exception as e:
            logging.warning(f"TX fetch failed for {signature[:12]}: {e}. Using heuristics only.")

        score, reasons = self.threat_detector.analyze_transaction(tx_data)

        if self.db:
            await self.db.log_threat(wallet_address, score, reasons, signature)

        if score >= config.RISK_SCORE_THRESHOLD:
            await self.notification_service.send_threat_alert(
                wallet_address=wallet_address,
                score=score,
                reasons=reasons,
                tx_hash=signature,
                user_id=user_id,
            )

            user_state_row = await self.db.get_user_state(user_id)
            if user_state_row:
                state = dict(user_state_row)
                auto_defense = state.get("auto_defense", False)

                if score >= 90 and auto_defense and self.emergency_service:
                    await self.notification_service.send_status_update(
                        "🔥 *CRITICAL THREAT: AUTO-DEFENSE TRIGGERED*"
                    )
                    await self.emergency_service.execute_all(user_id)
