import os
import logging
from cryptography.fernet import Fernet
import config
from utils.database import Database

class HardenedVaultManager:
    """
    Enhanced Vault that requires a transient 'Session Master Key'.
    This key is provided by the user at runtime/session start and is NEVER stored.
    It integrates with the Database for persistent encrypted storage.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HardenedVaultManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, session_key: str = None, db: Database = None):
        if not hasattr(self, 'initialized'):
            self.db = db or Database()
            if session_key:
                self.fernet = Fernet(session_key.encode())
            else:
                self.fernet = None
            self.initialized = True

    def is_unlocked(self):
        return self.fernet is not None

    def unlock(self, session_key: str):
        try:
            # Validate key format
            self.fernet = Fernet(session_key.encode())
            logging.info("🔓 Vault: Successfully unlocked with session key.")
            return True
        except Exception as e:
            logging.error(f"❌ Vault: Invalid session key format: {e}")
            self.fernet = None
            return False

    def lock(self):
        self.fernet = None
        logging.info("🔒 Vault: Session locked and key purged from memory.")

    async def store_key(self, wallet_address: str, private_key: str):
        """
        Encrypts a private key using the session key and stores it in the database.
        """
        if not self.fernet:
            raise PermissionError("Vault is locked. Cannot store keys.")
            
        encrypted_blob = self.fernet.encrypt(private_key.strip().encode())
        await self.db.store_vault_key(wallet_address, encrypted_blob.decode())
        logging.info(f"🔒 Vault: Key for {wallet_address} encrypted and persisted.")

    async def decrypt_key(self, wallet_address: str):
        """
        Retrieves and decrypts a key from the database using the session key.
        """
        if not self.fernet:
            raise PermissionError("Vault is locked. Session key required.")
            
        encrypted_blob_str = await self.db.get_vault_key(wallet_address)
        if not encrypted_blob_str:
            return None
            
        try:
            decrypted = self.fernet.decrypt(encrypted_blob_str.encode()).decode()
            return decrypted
        except Exception as e:
            logging.error(f"❌ Vault Decryption Error for {wallet_address}: {e}")
            return None
