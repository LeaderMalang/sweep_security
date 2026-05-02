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
    SHREDSTREAM_URL must be set in .env for this service to be active.
    """

    def __init__(self, threat_detector, notification_service, pre_signed_service=None, db=None):
        self.threat_detector = threat_detector
        self.notification_service = notification_service
        self.pre_signed_service = pre_signed_service
        self.db = db
        self.monitored_addresses = config.MONITORED_WALLETS

    async def start_solana_mempool(self):
        """Main loop for Solana mempool monitoring with reconnection logic."""
        if not config.SHREDSTREAM_URL:
            logging.warning(
                "Mempool: SHREDSTREAM_URL is not configured. "
                "Pre-inclusion defense is disabled. Set SHREDSTREAM_URL in .env to enable."
            )
            # Park this coroutine indefinitely rather than spamming logs
            while True:
                await asyncio.sleep(3600)
            return

        logging.info("📡 Mempool: Connecting to Solana Shredstream...")
        retry_delay = 1
        while True:
            try:
                await self._run_mempool_session()
                retry_delay = 1
            except Exception as e:
                logging.error(f"Mempool Connection lost: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _run_mempool_session(self):
        async with websockets.connect(config.SHREDSTREAM_URL) as websocket:
            while True:
                msg = await websocket.recv()
                tx = json.loads(msg)
                await self._analyze_pending_tx(tx)

    async def _analyze_pending_tx(self, tx_data):
        """Intercepts and counters attacks BEFORE block inclusion."""
        monitored_addresses: set = set()
        if self.db:
            users = await self.db.get_all_user_states()
            for u in users:
                user = dict(u)
                mon = json.loads(user.get("monitored_wallets_json", "[]") or "[]")
                monitored_addresses.update(mon)
        else:
            monitored_addresses = set(self.monitored_addresses)

        if not monitored_addresses:
            return

        if not any(addr in str(tx_data) for addr in monitored_addresses):
            return

        # analyze_transaction is synchronous
        score, reasons = self.threat_detector.analyze_transaction(tx_data)

        if score >= 90:
            logging.warning("🔥 CRITICAL PRE-INCLUSION THREAT!")
            await self.notification_service.send_status_update(
                "⚠️ *MEMPOOL ALERT: INTERCEPTING ATTACK*"
            )
            if self.pre_signed_service:
                target = tx_data.get("target", next(iter(monitored_addresses), None))
                if target:
                    await self.pre_signed_service.broadcast_immediate(target)
