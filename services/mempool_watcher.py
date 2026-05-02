import logging
import json
import websockets
import asyncio
import config
from utils.solana_client import SolanaClient

class MempoolWatcher:
    """
    High-Performance Mempool Watcher.
    Integrates with Helius/Jito Shredstream for Solana and Alchemy for EVM.
    """
    def __init__(self, threat_detector, notification_service, pre_signed_service=None):
        self.threat_detector = threat_detector
        self.notification_service = notification_service
        self.pre_signed_service = pre_signed_service
        self.monitored_addresses = config.MONITORED_WALLETS

    async def start_solana_mempool(self):
        """Main loop for Solana mempool monitoring with reconnection logic."""
        logging.info("📡 Mempool: Connecting to Solana Shredstream...")
        retry_delay = 1
        while True:
            try:
                # In production, SHREDSTREAM_URL would be configured
                if not hasattr(config, 'SHREDSTREAM_URL') or not config.SHREDSTREAM_URL:
                    logging.warning("Mempool: SHREDSTREAM_URL not configured. Skipping.")
                    await asyncio.sleep(60)
                    continue

                await self._run_mempool_session()
                retry_delay = 1
            except Exception as e:
                logging.error(f"Mempool Connection lost: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _run_mempool_session(self):
        """Internal logic for a single Shredstream WebSocket session."""
        async with websockets.connect(config.SHREDSTREAM_URL) as websocket:
            while True:
                msg = await websocket.recv()
                tx = json.loads(msg)
                await self._analyze_pending_tx(tx)

    async def _analyze_pending_tx(self, tx_data):
        """Intercepts and counters attacks BEFORE inclusion."""
        # 1. Fetch dynamic monitored addresses from DB
        monitored_addresses = set()
        if hasattr(self, 'db') and self.db:
            users = await self.db.get_all_user_states()
            for u in users:
                user = dict(u)
                mon = json.loads(user.get('monitored_wallets_json', '[]') or '[]')
                monitored_addresses.update(mon)
        else:
            monitored_addresses = set(self.monitored_addresses)

        if not monitored_addresses:
            return

        # Heuristic check for monitored address involvement
        if any(addr in str(tx_data) for addr in monitored_addresses):
            score = await self.threat_detector.analyze_transaction(tx_data)
            
            if score >= 90:
                logging.warning("🔥 CRITICAL PRE-INCLUSION THREAT!")
                await self.notification_service.send_status_update("⚠️ *MEMPOOL ALERT: INTERCEPTING ATTACK*")
                
                if self.pre_signed_service:
                    # RACE: Broadcast pre-signed sweep with massive priority fee
                    # Note: in real scenarios, 'target' should be extracted from tx_data
                    target = tx_data.get('target', self.monitored_addresses[0])
                    await self.pre_signed_service.broadcast_immediate(target)
