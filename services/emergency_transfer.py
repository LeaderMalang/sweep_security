from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit
from solders.message import Message, MessageV0
from solders.transaction import Transaction, VersionedTransaction
from utils.jito_client import JitoClient
import base58
import config
import logging
import json
import asyncio
from utils.signature_registry import SignatureRegistry

class EmergencyTransfer:
    def __init__(self, solana_client, jito_client=None, db=None):
        self.solana_client = solana_client
        self.jito_client = jito_client or JitoClient()
        self.db = db
        self.safe_wallet = Pubkey.from_string(config.SAFE_WALLET_ADDRESS) if config.SAFE_WALLET_ADDRESS else None
        self._gas_lock = asyncio.Lock()  # prevents concurrent refills from the same safe wallet

    async def _decrypt_wallet_key(self, wallet_address: str) -> str | None:
        """
        Decrypt a wallet private key using the vault (preferred) or static ENCRYPTION_KEY fallback.
        The vault must be unlocked for interactive sessions; automated tasks fall back to the
        static key so scheduled harvests work even when no user session is active.
        """
        from utils.vault_manager import HardenedVaultManager
        vault = HardenedVaultManager()
        if vault.is_unlocked():
            try:
                key = await vault.decrypt_key(wallet_address)
                if key:
                    return key
            except Exception as e:
                logging.warning(f"Vault decryption failed for {wallet_address}, trying fallback: {e}")

        # Fallback: static ENCRYPTION_KEY (used for automated/background operations)
        if config.ENCRYPTION_KEY:
            encrypted_blob = await self.db.get_vault_key(wallet_address)
            if encrypted_blob:
                try:
                    from utils.encryption_utils import EncryptionManager
                    return EncryptionManager(config.ENCRYPTION_KEY).decrypt(encrypted_blob).strip()
                except Exception as e:
                    logging.error(f"Static key decryption failed for {wallet_address}: {e}")
        return None

    async def execute_all(self, user_id: str):
        """Triggers a global sweep of all protected assets for a user."""
        db = self.db
        logging.warning(f"🚨 GLOBAL PANIC: execute_all triggered for user {user_id}")

        state_row = await db.get_user_state(user_id)
        if not state_row:
            logging.error("No user state found for sweep.")
            return False

        state = dict(state_row)
        if not state.get("monitored_wallets_json"):
            logging.error("No monitored wallets found for sweep.")
            return False

        wallets = json.loads(state["monitored_wallets_json"])
        tasks = []

        for address in wallets:
            privkey = await self._decrypt_wallet_key(address)
            if privkey:
                tasks.append(
                    self.sweep_all_sol_jito(privkey, user_id=user_id, db=db, retain_sol=0.0)
                )
            else:
                logging.error(f"Could not decrypt key for {address}. Skipping.")

        if not tasks:
            logging.error("No decryptable keys found in vault for any monitored wallet.")
            if hasattr(self, "notification_service") and self.notification_service:
                await self.notification_service.send_status_update(
                    "❌ *PANIC FAILED:* Vault is locked or no keys found. Run /unlock first."
                )
            return False

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        failure_count = len(tasks) - success_count

        logging.info(f"Global Panic Complete: {success_count}/{len(tasks)} wallets swept.")
        if failure_count > 0 and hasattr(self, "notification_service") and self.notification_service:
            await self.notification_service.send_status_update(
                f"⚠️ *PANIC PARTIAL:* {success_count} swept, {failure_count} failed."
            )
        return success_count > 0

    async def sweep_all_sol_jito(self, source_keypair_base58: str, user_id: str, db=None, retain_sol=0.0):
        """
        Transfers all SOL using a Jito bundle.
        Performs Auto-Refill if the source wallet is empty and the feature is enabled.
        """
        db = db or self.db
        if not self.safe_wallet:
            logging.error("Safe wallet address not configured.")
            return None

        # 1. Get User Tactical Settings
        state = await db.get_user_state(user_id) if db else {}
        state = dict(state) if state else {}
        tip_sol = state.get('jito_tip_sol', 0.001)
        
        # --- Dynamic Fee Escalation ---
        dynamic_tip = await self.solana_client.get_priority_fee_estimate(user_id)
        if dynamic_tip and dynamic_tip > tip_sol:
            logging.info(f"📈 Dynamic Fee Escalation: Scaling tip from {tip_sol} to {dynamic_tip:.6f} SOL based on network congestion.")
            tip_sol = dynamic_tip

        tip_lamports = int(tip_sol * 1_000_000_000)
        auto_refill = state.get('auto_refill_gas', 1)
        retain_lamports = int(retain_sol * 1_000_000_000)
        
        # Determine Destination
        destination = self.safe_wallet
        custom_safe = state.get('safe_wallet_address')
        if custom_safe:
            destination = Pubkey.from_string(custom_safe)

        client = await self.solana_client.get_client_for_user(user_id)
        source_keypair_base58 = source_keypair_base58.strip()
        try:
            source_kp = Keypair.from_base58_string(source_keypair_base58)
        except Exception as e:
            logging.error(f"❌ Key Decoding Failure: {str(e)} | Key Length: {len(source_keypair_base58)}")
            raise
        
        # 2. Gas Check & Auto-Refill
        balance = await self.solana_client.get_balance(source_kp.pubkey(), user_id)
        balance_lamports = int(balance * 1_000_000_000)
        min_required_lamports = 10000 + tip_lamports + retain_lamports # base fee + tip + retain

        try:
            if balance_lamports < min_required_lamports:
                if auto_refill:
                    logging.info(f"⛽ Auto-Refill: Injecting gas into {source_kp.pubkey()}...")
                    success = await self._inject_gas(source_kp.pubkey(), user_id, db)
                    if not success:
                        logging.error("Refill failed. Cannot sweep.")
                        return None
                    # Wait for refill confirmation
                    await asyncio.sleep(2)
                    balance = await self.solana_client.get_balance(source_kp.pubkey(), user_id)
                    balance_lamports = int(balance * 1_000_000_000)
                else:
                    logging.warning(f"Insufficient gas in {source_kp.pubkey()} and Auto-Refill is OFF.")
                    return None
            
            # 3. Dynamic Aggression (High Value Protection)
            # If rescuing > 1 SOL, ensure at least 0.005 tip — but never lower a higher dynamic tip
            if balance > 1.0:
                high_value_min = 0.005
                if tip_sol < high_value_min:
                    tip_sol = high_value_min
                    tip_lamports = 5_000_000
                    logging.warning(f"🚀 HIGH VALUE DETECTED ({balance} SOL). Ramping Tip to {tip_sol} SOL for maximum priority.")
                else:
                    logging.warning(f"🚀 HIGH VALUE DETECTED ({balance} SOL). Keeping dynamic tip {tip_sol:.6f} SOL.")

            # 3. Build sweep amounts
            # Jito path: deduct tip + tx fee + retain
            jito_amount = balance_lamports - tip_lamports - 5000 - retain_lamports
            # RPC fallback path: deduct only tx fee + retain (no tip wasted)
            fallback_amount = balance_lamports - 5000 - retain_lamports

            if jito_amount <= 0:
                logging.warning(f"Amount to send ({jito_amount}) is zero or negative. Skipping.")
                return None

            transfer_ix = transfer(TransferParams(
                from_pubkey=source_kp.pubkey(), to_pubkey=destination, lamports=jito_amount
            ))
            fallback_transfer_ix = transfer(TransferParams(
                from_pubkey=source_kp.pubkey(), to_pubkey=destination, lamports=fallback_amount
            ))

            # ── Fetch blockhash (used by both Jito and fallback TX) ──────────
            recent_blockhash = await self.solana_client.get_latest_blockhash(user_id)
            if not recent_blockhash:
                logging.error("Could not fetch blockhash. Aborting sweep.")
                return None

            # ── Build RPC Fallback TX (no tip — only the sweep) ─────────────
            fallback_message = MessageV0.try_compile(
                source_kp.pubkey(),
                [fallback_transfer_ix],
                [],
                recent_blockhash
            )
            fallback_tx = VersionedTransaction(fallback_message, [source_kp])

            # ── Build Jito Bundle TX (sweep + tip — atomic together) ─────────
            tip_account = self.jito_client.get_random_tip_account()
            tip_ix = transfer(TransferParams(
                from_pubkey=source_kp.pubkey(), to_pubkey=tip_account, lamports=tip_lamports
            ))
            jito_message = MessageV0.try_compile(
                source_kp.pubkey(),
                [transfer_ix, tip_ix],
                [],
                recent_blockhash
            )
            jito_tx = VersionedTransaction(jito_message, [source_kp])
            # Derive the actual on-chain tx signature from the signed transaction
            # (The bundle UUID returned by Jito differs from the real tx signature)
            actual_tx_sig = str(jito_tx.signatures[0])
            SignatureRegistry().register(actual_tx_sig)

            # ── Attempt Jito Bundle (tip only paid if this succeeds) ─────────
            bundle_id = await self.jito_client.send_bundle([jito_tx])
            if bundle_id:
                logging.info(f"🚀 Jito Bundle submitted! Bundle: {bundle_id} | TX: {actual_tx_sig}")
                confirmed = await self._await_bundle_confirmation(bundle_id)
                if confirmed:
                    logging.info(f"✅ Jito Bundle confirmed on-chain. TX: {actual_tx_sig}")
                    return actual_tx_sig
                logging.warning("⚠️ Jito bundle not confirmed within timeout. Falling back to RPC...")

            # ── Fallback: Standard RPC — NO tip sent ────────────────────────
            logging.warning("⚠️ Falling back to tip-free standard RPC broadcast...")
            signature = await self.solana_client.send_raw_transaction(bytes(fallback_tx), user_id)
            if signature:
                SignatureRegistry().register(signature)
                logging.info(f"✅ Fallback Sweep Success! (No Jito tip paid) Sig: {signature}")
                return signature

            return None
        except Exception as e:
            logging.error(f"Sweep failed: {e}")
            return None
        finally:
            if user_id and client != self.solana_client.client:
                await client.close()

    async def _await_bundle_confirmation(self, bundle_id: str, timeout_secs: int = 20) -> bool:
        """Polls getBundleStatuses every 1.5s until confirmed/finalized or timeout."""
        import time
        deadline = time.monotonic() + timeout_secs
        while time.monotonic() < deadline:
            await asyncio.sleep(1.5)
            try:
                statuses = await self.jito_client.get_bundle_statuses([bundle_id])
                for s in statuses:
                    if s.get("bundle_id") == bundle_id:
                        status = s.get("confirmation_status", "")
                        if status in ("confirmed", "finalized"):
                            return True
                        err = s.get("err")
                        if err and err not in (None, {"Ok": None}):
                            logging.error(f"Jito bundle error: {err}")
                            return False
            except Exception as e:
                logging.warning(f"Bundle status poll error: {e}")
        logging.warning(f"Jito bundle {bundle_id[:16]}... timed out after {timeout_secs}s.")
        return False

    async def _inject_gas(self, target_pubkey, user_id, db):
        """Sends a small amount of SOL from the safe wallet to the target.
        Serialized via _gas_lock to prevent concurrent refills from the same source wallet."""
        async with self._gas_lock:
            try:
                # 1. Try to get user's personal gas key first
                row = await db.get_user_state(user_id)
                state = dict(row) if row else {}
                user_safe_addr = state.get('safe_wallet_address')

                privkey = None
                if user_safe_addr:
                    encrypted_key = await db.get_vault_key(user_safe_addr)
                    if encrypted_key:
                        from utils.encryption_utils import EncryptionManager
                        encryptor = EncryptionManager(config.ENCRYPTION_KEY)
                        privkey = encryptor.decrypt(encrypted_key).strip()

                # 2. Fallback to System Global Key
                if not privkey:
                    raw = config.SAFE_WALLET_PRIVATE_KEY  # may be None if not set in .env
                    privkey = raw.strip() if raw else None

                if not privkey:
                    logging.error("No gas source (user or global) available for refill.")
                    return False

                safe_kp = Keypair.from_base58_string(privkey)
                balance = await self.solana_client.get_balance(safe_kp.pubkey(), user_id)
                if balance < 0.006:
                    logging.error(f"❌ GAS TANK EMPTY: {safe_kp.pubkey()} only has {balance} SOL.")
                    return False

                # Inject 0.007 SOL (covers high-priority tip + base fee)
                refill_ix = transfer(TransferParams(
                    from_pubkey=safe_kp.pubkey(),
                    to_pubkey=target_pubkey,
                    lamports=7_000_000
                ))
                recent_blockhash = await self.solana_client.get_latest_blockhash(user_id)
                if not recent_blockhash:
                    return False

                message = MessageV0.try_compile(safe_kp.pubkey(), [refill_ix], [], recent_blockhash)
                tx = VersionedTransaction(message, [safe_kp])

                logging.info(f"⛽ [Refill] Broadcasting injection to {target_pubkey}...")
                res = await self.solana_client.send_raw_transaction(bytes(tx), user_id)
                if not res:
                    logging.error(f"⛽ Gas injection TX rejected by RPC for user {user_id}.")
                    return False
                SignatureRegistry().register(res)
                logging.info(f"⛽ Gas injected for user {user_id}: {res}")
                return True
            except Exception as e:
                logging.error(f"Gas Injection Error: {e}")
                return False
