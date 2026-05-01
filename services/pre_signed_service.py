import logging
from solders.transaction import Transaction
from solders.message import Message, MessageV0
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
import config

class PreSignedService:
    """
    Manages pre-staged transaction templates for ultra-fast broadcasting.
    On Solana, blockhashes expire, so we use Nonce Accounts or 
    pre-built Message structures to minimize signing time.
    """
    def __init__(self, solana_client):
        self.solana_client = solana_client
        self.templates = {} # wallet_address -> signed_tx_hex
        from services.nonce_manager import NonceManager
        self.nonce_manager = NonceManager(solana_client)

    async def prepare_solana_template(self, from_pubkey, to_pubkey, amount_lamports, nonce_account=None, user_id=None):
        """
        Builds a transaction message using a Durable Nonce for zero-latency broadcast.
        If no nonce is provided, it can fall back to a standard blockhash (legacy).
        """
        instructions = []
        recent_blockhash = None
        
        # 1. Handle Durable Nonce Logic
        if nonce_account:
            info = await self.nonce_manager.get_nonce_info(nonce_account, user_id)
            if info:
                logging.info(f"⚡ [Hardening] Using Durable Nonce for {from_pubkey}: {info['nonce']}")
                # Add Advance instruction (MUST be first)
                instructions.append(self.nonce_manager.get_advance_instruction(nonce_account, str(info['authority'])))
                recent_blockhash = Pubkey.from_string(info['nonce'])
        
        # 2. Add Sweep Instruction
        instructions.append(transfer(TransferParams(
            from_pubkey=Pubkey.from_string(from_pubkey),
            to_pubkey=Pubkey.from_string(to_pubkey),
            lamports=amount_lamports
        )))

        # 3. Fallback to Blockhash if no nonce
        if not recent_blockhash:
            logging.warning("⚠️ No Durable Nonce found. Falling back to 60s blockhash.")
            recent_blockhash = await self.solana_client.get_latest_blockhash(user_id)

        if not recent_blockhash:
            return None

        message = MessageV0.new_with_blockhash(
            instructions,
            Pubkey.from_string(from_pubkey),
            recent_blockhash
        )
        return message

    def store_signed_tx(self, wallet_address, signed_hex):
        """Stores a pre-signed transaction for immediate broadcast."""
        self.templates[wallet_address] = signed_hex
        logging.info(f"🚀 Pre-staged: Signed TX ready for {wallet_address}")

    async def broadcast_immediate(self, wallet_address):
        """Broadcasts the pre-staged transaction to multiple RPCs."""
        if wallet_address not in self.templates:
            logging.error(f"No pre-staged TX for {wallet_address}")
            return False
            
        signed_hex = self.templates[wallet_address]
        logging.info(f"🔥 PANIC: Broadcasting pre-staged TX for {wallet_address}...")
        
        # In a real implementation, this would send to multiple endpoints
        try:
            from solders.transaction import VersionedTransaction
            import base64
            tx_bytes = base64.b64decode(signed_hex)
            sig = await self.solana_client.send_raw_transaction(tx_bytes)
            return sig
        except Exception as e:
            logging.error(f"Immediate broadcast failed: {e}")
            return False
