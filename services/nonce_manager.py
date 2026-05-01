import logging
from solders.pubkey import Pubkey
from solders.system_program import advance_nonce_account, AdvanceNonceAccountParams
from solders.instruction import Instruction
import config

class NonceManager:
    def __init__(self, solana_client):
        self.solana_client = solana_client

    async def get_nonce_info(self, nonce_account_address: str, user_id: str = None):
        """
        Fetches the current nonce value and authority from a nonce account.
        """
        account_info = await self.solana_client.get_account_info(nonce_account_address, user_id)
        if not account_info:
            logging.error(f"Nonce account {nonce_account_address} not found.")
            return None
            
        # Nonce accounts are 80 bytes. 
        # Structure: [0:4] Version, [4:8] State (1 for initialized), [8:40] Authorized Pubkey, [40:72] Nonce, [72:80] Fee Calculator
        data = account_info.data
        if len(data) < 80:
            logging.error(f"Invalid nonce account data length: {len(data)}")
            return None
            
        # Parse state
        state = int.from_bytes(data[4:8], "little")
        if state != 1:
            logging.error(f"Nonce account {nonce_account_address} is not initialized.")
            return None
            
        authorized_pubkey = Pubkey(data[8:40])
        nonce_value = Pubkey(data[40:72])
        
        return {
            "address": nonce_account_address,
            "authority": authorized_pubkey,
            "nonce": str(nonce_value)
        }

    def get_advance_instruction(self, nonce_account_address: str, authorized_pubkey: str) -> Instruction:
        """
        Creates the instruction to advance the nonce. 
        Must be the first instruction in a transaction using a nonce.
        """
        return advance_nonce_account(AdvanceNonceAccountParams(
            nonce_pubkey=Pubkey.from_string(nonce_account_address),
            authorized_pubkey=Pubkey.from_string(authorized_pubkey)
        ))
