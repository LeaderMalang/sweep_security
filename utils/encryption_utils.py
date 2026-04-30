from cryptography.fernet import Fernet
import base64
import logging

class EncryptionManager:
    def __init__(self, key_str):
        """
        Uses Fernet (AES-128 in CBC mode with HMAC) for simple, secure encryption.
        key_str must be a URL-safe base64-encoded 32-byte key.
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
