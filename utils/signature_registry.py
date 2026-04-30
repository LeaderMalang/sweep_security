import time
import logging

class SignatureRegistry:
    _instance = None
    _whitelist = {} # sig -> expiration_timestamp

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SignatureRegistry, cls).__new__(cls)
        return cls._instance

    def register(self, signature: str, ttl: int = 300):
        """Adds a signature to the whitelist with a Time-To-Live (default 5 mins)."""
        if not signature: return
        logging.info(f"🛡️ WHITELISTED: {signature[:10]}... registered for {ttl}s.")
        self._whitelist[signature] = time.time() + ttl

    def is_whitelisted(self, signature: str) -> bool:
        """Checks if a signature is in the whitelist and hasn't expired."""
        if signature in self._whitelist:
            if time.time() < self._whitelist[signature]:
                return True
            else:
                del self._whitelist[signature] # Clean up expired
        return False

    def prune(self):
        """Removes all expired signatures."""
        now = time.time()
        expired = [s for s, t in self._whitelist.items() if t < now]
        for s in expired:
            del self._whitelist[s]
