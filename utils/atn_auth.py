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
            private_key = f.read()
            
        payload = {
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600 # Valid for 1 hour
        }
        
        headers = {
            "alg": "RS256",
            "typ": "JWT",
            "kid": kid
        }
        
        # Sign with RS256 as per the .pem file provided
        token = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
        return token
    except Exception as e:
        logging.error(f"⚠️ Failed to generate ATN JWT: {e}")
        return None
