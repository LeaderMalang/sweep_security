import jwt
import time
import os
import logging

def get_atn_jwt():
    """
    Generates a JWT for All That Node RPC using RS256 and the private.pem file.
    """
    kid = os.getenv("ATN_RPC_KID", "f68b1708-26e3-11f1-86ff-06e9eb796a53")
    pem_path = "private.pem"
    
    if not os.path.exists(pem_path):
        logging.warning(f"❌ ATN Auth: private.pem not found at {os.path.abspath(pem_path)}")
        return None
        
    try:
        with open(pem_path, "r") as f:
            private_key = f.read().strip()
            
        now = int(time.time())
        payload = {
            "iat": now - 60,   # 1 minute buffer
            "nbf": now - 60,   # Valid immediately
            "exp": now + 3600, # 1 hour expiry
            "aud": "allthatnode.com"
        }
        
        headers = {
            "alg": "RS256",
            "typ": "JWT",
            "kid": kid
        }
        
        # Sign with RS256
        token = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
        
        # Ensure token is a string (PyJWT 2.0+ returns str, but let's be safe)
        if isinstance(token, bytes):
            token = token.decode('utf-8')
            
        return token
    except Exception as e:
        logging.error(f"⚠️ Failed to generate ATN JWT: {e}")
        return None
