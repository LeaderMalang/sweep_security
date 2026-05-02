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

    # SPL Token Program IDs — same set used by wallet_monitor and threat_detector
    _TOKEN_PROGRAMS = {
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbEquAZkGfyQ3VaHHMGKKCJRFnxPgGHCCBW",
    }

    async def _analyze_pending_tx(self, raw):
        """
        Parses raw Shredstream JSON into the tx_data format expected by
        ThreatDetector.analyze_transaction(), then scores it.

        Shredstream delivers a dict with at least:
          raw["transaction"]["message"]["accountKeys"]  — list of pubkey strings
          raw["transaction"]["message"]["instructions"] — list of {programIdIndex, ...}
          raw["meta"]["preBalances"] / raw["meta"]["postBalances"]
          raw["meta"]["innerInstructions"]
        Fields vary by Shredstream provider; we defensively fall back to 0/[].
        """
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

        raw_str = json.dumps(raw)
        if not any(addr in raw_str for addr in monitored_addresses):
            return

        # ── Parse Shredstream fields ───────────────────────────────────────────
        msg = raw.get("transaction", {}).get("message", {})
        meta = raw.get("meta", {})

        account_keys: list = msg.get("accountKeys", [])
        instructions: list = msg.get("instructions", [])
        inner_ixs: list = meta.get("innerInstructions", [])
        pre_balances: list = meta.get("preBalances", [])
        post_balances: list = meta.get("postBalances", [])

        sender = account_keys[0] if account_keys else "Unknown"
        ix_count = len(instructions)
        inner_count = sum(len(ii.get("instructions", [])) for ii in inner_ixs)

        program_ids: list = []
        for ix in instructions:
            idx = ix.get("programIdIndex", -1)
            if 0 <= idx < len(account_keys):
                program_ids.append(account_keys[idx])

        is_spl = bool(set(program_ids) & self._TOKEN_PROGRAMS)

        # Balance delta for the first monitored wallet found in account keys
        amount = 0.0
        target = None
        for addr in monitored_addresses:
            if addr in account_keys:
                target = addr
                w_idx = account_keys.index(addr)
                if w_idx < len(pre_balances) and w_idx < len(post_balances):
                    delta = pre_balances[w_idx] - post_balances[w_idx]
                    amount = abs(delta) / 1e9
                break

        tx_data = {
            "amount": amount,
            "sender": sender,
            "network": "solana",
            "instruction_count": ix_count,
            "inner_instruction_count": inner_count,
            "is_spl_token": is_spl,
            "program_ids": program_ids,
            "token_name": "",
            "input": "",
        }

        score, reasons = self.threat_detector.analyze_transaction(tx_data)

        if score >= 90:
            logging.warning(f"🔥 CRITICAL PRE-INCLUSION THREAT! Score={score}  {reasons}")
            await self.notification_service.send_status_update(
                "⚠️ *MEMPOOL ALERT: INTERCEPTING ATTACK*"
            )
            if self.pre_signed_service:
                dest = target or next(iter(monitored_addresses), None)
                if dest:
                    await self.pre_signed_service.broadcast_immediate(dest)
