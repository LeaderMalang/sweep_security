import time
import logging
from collections import defaultdict
from threading import Lock
from cryptography.fernet import Fernet
from utils.database import Database


class _RateLimiter:
    """Tracks failed unlock attempts per identifier to block brute-force attacks."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict = defaultdict(list)
        self._lock = Lock()

    def is_limited(self, identifier: str) -> bool:
        with self._lock:
            now = time.monotonic()
            recent = [t for t in self._failures[identifier] if now - t < self.window_seconds]
            self._failures[identifier] = recent
            return len(recent) >= self.max_failures

    def record_failure(self, identifier: str):
        with self._lock:
            self._failures[identifier].append(time.monotonic())

    def clear(self, identifier: str):
        with self._lock:
            self._failures.pop(identifier, None)


_unlock_limiter = _RateLimiter(max_failures=5, window_seconds=300)


class HardenedVaultManager:
    """
    Vault that requires a transient Session Master Key.
    The key is provided at runtime and is never persisted to disk.
    Brute-force protection: 5 failed unlock attempts per IP locks out for 5 minutes.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HardenedVaultManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, session_key: str = None, db: Database = None):
        if not hasattr(self, "initialized"):
            self.db = db or Database()
            self.fernet = Fernet(session_key.encode()) if session_key else None
            self.initialized = True

    def is_unlocked(self) -> bool:
        return self.fernet is not None

    def unlock(self, session_key: str, identifier: str = "default") -> bool:
        """Validate and store the session key. Returns False if rate-limited or key is invalid."""
        if _unlock_limiter.is_limited(identifier):
            logging.warning(f"🔒 Vault: Rate limit active for {identifier}. Too many failed attempts.")
            return False
        try:
            self.fernet = Fernet(session_key.encode())
            _unlock_limiter.clear(identifier)
            logging.info("🔓 Vault: Successfully unlocked.")
            return True
        except Exception as e:
            logging.error(f"❌ Vault: Invalid session key from {identifier}: {e}")
            _unlock_limiter.record_failure(identifier)
            self.fernet = None
            return False

    def lock(self):
        self.fernet = None
        logging.info("🔒 Vault: Session locked and key purged from memory.")

    async def store_key(self, wallet_address: str, private_key: str):
        if not self.fernet:
            raise PermissionError("Vault is locked. Cannot store keys.")
        encrypted_blob = self.fernet.encrypt(private_key.strip().encode())
        await self.db.store_vault_key(wallet_address, encrypted_blob.decode())
        logging.info(f"🔒 Vault: Key for {wallet_address} encrypted and stored.")

    async def decrypt_key(self, wallet_address: str) -> str | None:
        if not self.fernet:
            raise PermissionError("Vault is locked. Session key required.")
        encrypted_blob_str = await self.db.get_vault_key(wallet_address)
        if not encrypted_blob_str:
            return None
        try:
            return self.fernet.decrypt(encrypted_blob_str.encode()).decode()
        except Exception as e:
            logging.error(f"❌ Vault: Decryption failed for {wallet_address}: {e}")
            return None
