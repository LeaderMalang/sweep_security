from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit
from solders.message import Message
from solders.transaction import Transaction
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

    async def execute_all(self, user_id: str):
        """Triggers a global sweep of all protected assets for a user."""
        db = self.db
        logging.warning(f"🚨 GLOBAL PANIC: execute_all triggered for user {user_id}")
        
        from utils.encryption_utils import EncryptionManager
        encryptor = EncryptionManager(config.ENCRYPTION_KEY)
        
        state = await db.get_user_state(user_id)
        if not state or not state['monitored_wallets_json']:
            logging.error("No monitored wallets found for sweep.")
            return False

        wallets = json.loads(state['monitored_wallets_json'])
        tasks = []
        
        for address in wallets:
            encrypted_key = await db.get_vault_key(address)
            if encrypted_key:
                try:
                    privkey = encryptor.decrypt(encrypted_key).strip()
                    retain = state.get('skimming_retain', 0.0)
                    tasks.append(self.sweep_all_sol_jito(privkey, user_id=user_id, db=db, retain_sol=retain))
                except Exception as e:
                    logging.error(f"Failed to decrypt key for {address}: {e}")
        
        if not tasks:
            logging.error("No valid keys found in vault for any wallet.")
            return False

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        
        logging.info(f"Global Panic Complete: {success_count}/{len(tasks)} wallets swept.")
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
            # If rescuing > 1 SOL, force a 0.005 tip for maximum safety
            if balance > 1_000_000_000:
                logging.warning(f"🚀 HIGH VALUE DETECTED ({balance/1e9} SOL). Ramping Tip to 0.005 SOL for maximum priority.")
                tip_sol = 0.005
                tip_lamports = 5_000_000

            # 3. Execute Sweep
            amount_to_send = balance - tip_lamports - 5000 - retain_lamports
            if amount_to_send <= 0: return None

            transfer_ix = transfer(TransferParams(
                from_pubkey=source_kp.pubkey(), to_pubkey=destination, lamports=amount_to_send
            ))
            tip_account = self.jito_client.get_random_tip_account()
            tip_ix = transfer(TransferParams(
                from_pubkey=source_kp.pubkey(), to_pubkey=tip_account, lamports=tip_lamports
            ))

            recent_blockhash = await self.solana_client.get_latest_blockhash(user_id)
            if not recent_blockhash: return None

            msg = Message.new_with_blockhash(
                [transfer_ix, tip_ix],
                source_kp.pubkey(),
                recent_blockhash
            )
            tx = Transaction([source_kp], msg, recent_blockhash)

            signature = await self.jito_client.send_bundle([tx])
            if signature:
                SignatureRegistry().register(signature)
                logging.info(f"🚀 Rescue Bundle Sent! Tip: {tip_sol} SOL. Sig: {signature}")
                return signature
            
            # FALLBACK: If Jito fails, send via regular RPC
            logging.warning("⚠️ Jito Bundle failed. Falling back to standard RPC broadcast...")
            signature = await self.solana_client.send_raw_transaction(bytes(tx), user_id)
            if signature:
                SignatureRegistry().register(signature)
                logging.info(f"✅ Fallback Sweep Success! Sig: {signature}")
                return signature

            return None
        except Exception as e:
            logging.error(f"Sweep failed: {e}")
            return None
        finally:
            if user_id and client != self.solana_client.client:
                await client.close()

    async def _inject_gas(self, target_pubkey, user_id, db):
        """Sends a small amount of SOL from the safe wallet to the target."""
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
                    privkey = encryptor.decrypt(encrypted_key)

            # 2. Fallback to System Global Key
            if not privkey:
                privkey = config.SAFE_WALLET_PRIVATE_KEY
            
            if not privkey:
                logging.error("No gas source (user or global) available for refill.")
                return False

            safe_kp = Keypair.from_base58_string(privkey)
            # 2.5 Balance Check for Gas Source
            balance = await self.solana_client.get_balance(safe_kp.pubkey(), user_id)
            if balance < 0.006: # 0.005 + fee
                logging.error(f"❌ GAS TANK EMPTY: {safe_kp.pubkey()} only has {balance} SOL. Please fund it for Auto-Refill.")
                return False

            # Inject 0.005 SOL (enough for multiple rescue attempts)
            refill_ix = transfer(TransferParams(
                from_pubkey=safe_kp.pubkey(),
                to_pubkey=target_pubkey,
                lamports=5_000_000 
            ))
            recent_blockhash = await self.solana_client.get_latest_blockhash(user_id)
            if not recent_blockhash: return False

            msg = Message.new_with_blockhash(
                [refill_ix],
                safe_kp.pubkey(),
                recent_blockhash
            )
            tx = Transaction([safe_kp], msg, recent_blockhash)
            
            res = await self.solana_client.send_raw_transaction(bytes(tx), user_id)
            logging.info(f"⛽ Gas Injected for user {user_id}: {res}")
            return True
        except Exception as e:
            logging.error(f"Gas Injection Error: {e}")
            return False
