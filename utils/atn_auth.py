import jwt
import time
import os
import logging


def get_atn_jwt() -> str | None:
    """
    Generates a JWT for All That Node RPC using RS256 and private.pem.
    Returns None if the key file is missing or signing fails; callers must handle None.
    """
    kid = os.getenv("ATN_RPC_KID", "")
    pem_path = "private.pem"

    if not os.path.exists(pem_path):
        # Log once at DEBUG level — this is a normal state when ATN is not configured
        logging.debug("ATN Auth: private.pem not found; ATN JWT will not be attached to RPC requests.")
        return None

    try:
        with open(pem_path, "r") as f:
            private_key = f.read().strip()

        if not private_key:
            logging.error("ATN Auth: private.pem is empty. Cannot generate JWT.")
            return None

        now = int(time.time())
        payload = {
            "iat": now - 60,
            "nbf": now - 60,
            "exp": now + 3600,
            "aud": "allthatnode.com",
        }
        headers = {"alg": "RS256", "typ": "JWT", "kid": kid}

        token = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
        return token if isinstance(token, str) else token.decode("utf-8")
    except Exception as e:
        logging.error(f"ATN Auth: Failed to generate JWT: {e}")
        return None
