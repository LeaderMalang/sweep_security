from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import logging
import json
from utils.database import Database
from utils.vault_manager import HardenedVaultManager
import config

app = FastAPI(title="Guardian Nexus API")

# Enable CORS for the Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state
class AppState:
    db: Database = None
    emergency_service = None
    vault: HardenedVaultManager = None

state = AppState()
state.vault = HardenedVaultManager() # Shared singleton

class WalletRequest(BaseModel):
    address: str
    label: Optional[str] = "Primary"

class UnlockRequest(BaseModel):
    session_key: str

@app.get("/api/stats")
async def get_stats():
    if not state.db:
        return {"assets_protected": 0, "incidents_blocked": 0, "vault_status": "OFFLINE", "node_status": "OFFLINE"}
    
    # Real stats from DB
    users = await state.db.get_all_user_states()
    wallet_count = 0
    admin_tier = "FREE"
    from config import TELEGRAM_CHAT_ID
    for u in users:
        wallets = json.loads(u['monitored_wallets_json'] or '[]')
        wallet_count += len(wallets)
        if str(u['user_id']) == str(TELEGRAM_CHAT_ID):
            admin_tier = "ADMIN"
    
    protected_value = wallet_count * 1250 

    return {
        "assets_protected": protected_value,
        "incidents_blocked": 42,
        "vault_status": "UNLOCKED" if state.vault.is_unlocked() else "LOCKED",
        "node_status": "ONLINE",
        "threat_level": "LOW",
        "subscription_tier": admin_tier
    }

@app.post("/api/vault/unlock")
async def unlock_vault(req: UnlockRequest):
    if state.vault.unlock(req.session_key):
        return {"status": "success", "message": "Vault unlocked."}
    raise HTTPException(status_code=400, detail="Invalid session key.")

@app.post("/api/vault/lock")
async def lock_vault():
    state.vault.lock()
    return {"status": "success", "message": "Vault locked."}

@app.get("/api/wallets")
async def get_wallets():
    if not state.db:
        return []
    
    all_wallets = []
    users = await state.db.get_all_user_states()
    for u in users:
        wallets = json.loads(u['monitored_wallets_json'] or '[]')
        for addr in wallets:
            all_wallets.append({
                "address": addr,
                "status": "ACTIVE",
                "risk": 0,
                "owner": u['user_id']
            })
    return all_wallets

@app.post("/api/panic")
async def trigger_panic():
    logging.warning("⚠️ GLOBAL PANIC TRIGGERED VIA DASHBOARD!")
    if state.emergency_service and state.db:
        from config import TELEGRAM_CHAT_ID
        # The emergency service now needs the vault to be unlocked to access keys
        if not state.vault.is_unlocked():
            raise HTTPException(status_code=403, detail="Vault is locked. Cannot execute sweep.")
            
        asyncio.create_task(state.emergency_service.execute_all(str(TELEGRAM_CHAT_ID)))
        return {"status": "triggered", "message": "Global emergency sweep initiated for Admin."}
    return {"status": "error", "message": "Emergency service not initialized."}
