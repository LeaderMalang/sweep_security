from cryptography.fernet import Fernet
import base64
import logging

class EncryptionManager:
    def __init__(self, key_str):
        """
        Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
        key_str must be a URL-safe base64-encoded 32-byte key (generate with Fernet.generate_key()).
        Note: Fernet uses AES-128, not AES-256. Use for background/static key operations only;
        prefer HardenedVaultManager for interactive sessions.
        """
        try:
            # Ensure the key is in the correct format for Fernet
            self.cipher_suite = Fernet(key_str.encode() if isinstance(key_str, str) else key_str)
        except Exception as e:
            logging.error(f"Encryption Init Error: {e}")
            raise

    def encrypt(self, data: str) -> str:
        """Encrypts a string and returns a base64 string."""
        return self.cipher_suite.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypts a base64 string and returns the original string."""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
