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

class EmergencyTransfer:
    def __init__(self, solana_client, jito_client=None):
        self.solana_client = solana_client
        self.jito_client = jito_client or JitoClient()
        self.safe_wallet = Pubkey.from_string(config.SAFE_WALLET_ADDRESS) if config.SAFE_WALLET_ADDRESS else None

    async def execute_all(self):
        """Triggers a global sweep of all protected assets."""
        logging.warning("🚨 GLOBAL PANIC: execute_all triggered.")
        # In a real scenario, this would fetch encrypted keys from the DB
        return False

    async def sweep_all(self, wallet_address, destination):
        """Sweeps a specific wallet to a destination."""
        logging.info(f"🚀 Manual sweep initiated for {wallet_address} -> {destination}")
        return False

    async def sweep_all_sol_jito(self, source_keypair_base58: str, tip_amount_lamports: int = 100000):
        """
        Transfers all SOL using a Jito bundle for maximum security and speed.
        """
        if not self.safe_wallet:
            logging.error("Safe wallet address not configured.")
            return None

        try:
            keypair = Keypair.from_base58_string(source_keypair_base58)
        except Exception as e:
            logging.error(f"Invalid private key: {e}")
            return None

        # 1. Get current balance
        balance_resp = await self.solana_client.client.get_balance(keypair.pubkey())
        balance = balance_resp.value

        # Fees: base + tip
        total_fees = 5000 + tip_amount_lamports
        
        if balance <= total_fees:
            logging.warning("Insufficient balance to sweep with Jito tip.")
            return None

        amount_to_send = balance - total_fees
        
        # 2. Construct Instructions
        # Instruction A: Transfer to Safe Wallet
        transfer_ix = transfer(TransferParams(
            from_pubkey=keypair.pubkey(),
            to_pubkey=self.safe_wallet,
            lamports=amount_to_send
        ))

        # Instruction B: Jito Tip
        tip_account = self.jito_client.get_random_tip_account()
        tip_ix = transfer(TransferParams(
            from_pubkey=keypair.pubkey(),
            to_pubkey=tip_account,
            lamports=tip_amount_lamports
        ))

        # 3. Create transaction
        recent_blockhash = await self.solana_client.client.get_latest_blockhash()
        tx = Transaction()
        tx.add(transfer_ix)
        tx.add(tip_ix)
        tx.recent_blockhash = recent_blockhash.value.blockhash

        # 4. Send via Jito
        # We need the signed transaction bytes
        tx.sign(keypair)
        bundle_id = await self.jito_client.send_bundle([tx])
        
        if bundle_id:
            logging.info(f"🚀 Jito Emergency Bundle sent! ID: {bundle_id}")
            return bundle_id
        return None
