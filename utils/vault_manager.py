import os
import logging
from cryptography.fernet import Fernet
import config

class HardenedVaultManager:
    """
    Enhanced Vault that requires a transient 'Session Master Key'.
    This key is provided by the user at runtime/session start and is NEVER stored.
    """
    def __init__(self, session_key: str = None):
        if session_key:
            self.fernet = Fernet(session_key.encode())
        else:
            self.fernet = None
        self._vault = {} 

    def is_unlocked(self):
        return self.fernet is not None

    def unlock(self, session_key: str):
        try:
            self.fernet = Fernet(session_key.encode())
            logging.info("🔓 Vault: Successfully unlocked with session key.")
            return True
        except Exception:
            logging.error("❌ Vault: Invalid session key.")
            return False

    def store_encrypted_blob(self, wallet_address: str, encrypted_blob: bytes):
        """Stores an already encrypted blob (encrypted on client-side)."""
        self._vault[wallet_address] = encrypted_blob
        logging.info(f"🔒 Vault: Stored client-encrypted blob for {wallet_address}")

    def decrypt_key(self, wallet_address: str):
        """Decrypts a stored blob using the session key."""
        if not self.fernet:
            raise PermissionError("Vault is locked. Session key required.")
            
        if wallet_address not in self._vault:
            return None
            
        encrypted_blob = self._vault[wallet_address]
        return self.fernet.decrypt(encrypted_blob).decode()
