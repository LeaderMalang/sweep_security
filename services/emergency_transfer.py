from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit
from solders.transaction import Transaction
from utils.jito_client import JitoClient
import base58
import config
import logging
import json
import asyncio

class EmergencyTransfer:
    def __init__(self, solana_client, jito_client=None):
        self.solana_client = solana_client
        self.jito_client = jito_client or JitoClient()
        self.safe_wallet = Pubkey.from_string(config.SAFE_WALLET_ADDRESS) if config.SAFE_WALLET_ADDRESS else None

    async def execute_all(self, user_id: str, db):
        """Triggers a global sweep of all protected assets for a user."""
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
                    privkey = encryptor.decrypt(encrypted_key)
                    tasks.append(self.sweep_all_sol_jito(privkey, user_id=user_id))
                except Exception as e:
                    logging.error(f"Failed to decrypt key for {address}: {e}")
        
        if not tasks:
            logging.error("No valid keys found in vault for any wallet.")
            return False

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        
        logging.info(f"Global Panic Complete: {success_count}/{len(tasks)} wallets swept.")
        return success_count > 0

    async def sweep_all_sol_jito(self, source_keypair_base58: str, user_id: str = None, tip_amount_lamports: int = 100000):
        """
        Transfers all SOL using a Jito bundle for maximum security and speed.
        Uses the user's custom RPC if user_id is provided.
        """
        if not self.safe_wallet:
            logging.error("Safe wallet address not configured.")
            return None

        # Get correct client for this user
        client = await self.solana_client.get_client_for_user(user_id) if user_id else self.solana_client.client

        try:
            keypair = Keypair.from_base58_string(source_keypair_base58)
            
            # 1. Get current balance
            balance_resp = await client.get_balance(keypair.pubkey())
            balance = balance_resp.value

            # Fees: base + tip
            total_fees = 5000 + tip_amount_lamports
            
            if balance <= total_fees:
                logging.warning("Insufficient balance to sweep with Jito tip.")
                return None

            amount_to_send = balance - total_fees
            
            # 2. Construct Instructions
            transfer_ix = transfer(TransferParams(
                from_pubkey=keypair.pubkey(),
                to_pubkey=self.safe_wallet,
                lamports=amount_to_send
            ))

            tip_account = self.jito_client.get_random_tip_account()
            tip_ix = transfer(TransferParams(
                from_pubkey=keypair.pubkey(),
                to_pubkey=tip_account,
                lamports=tip_amount_lamports
            ))

            # 3. Create transaction
            recent_blockhash = await client.get_latest_blockhash()
            tx = Transaction()
            tx.add(transfer_ix)
            tx.add(tip_ix)
            tx.recent_blockhash = recent_blockhash.value.blockhash

            # 4. Send via Jito
            tx.sign(keypair)
            bundle_id = await self.jito_client.send_bundle([tx])
            
            if bundle_id:
                logging.info(f"🚀 Jito Emergency Bundle sent! ID: {bundle_id}")
                return bundle_id
            return None
        finally:
            # If we created a temporary client, we should close it
            if user_id and client != self.solana_client.client:
                await client.close()
