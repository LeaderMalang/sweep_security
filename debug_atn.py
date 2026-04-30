import asyncio
import httpx
import os
from utils.atn_auth import get_atn_jwt
import config

async def test_rpc():
    print("🧪 Starting ATN RPC Debug Test...")
    
    url = config.SOLANA_RPC_URL
    token = get_atn_jwt()
    
    if not token:
        print("❌ Error: Could not generate JWT. Check private.pem.")
        return

    print(f"✅ JWT Generated (First 20 chars): {token[:20]}...")
    print(f"🔗 Testing URL: {url}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getHealth"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            print(f"📡 Status Code: {response.status_code}")
            print(f"📦 Response Body: {response.text}")
            
            if response.status_code == 200:
                print("🎉 SUCCESS! The JWT and URL are correct.")
            else:
                print("❌ FAILED. Look at the response body above for the reason.")
                
        except Exception as e:
            print(f"💥 Request Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_rpc())
