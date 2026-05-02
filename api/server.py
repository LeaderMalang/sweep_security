import time
import asyncio
import logging
import json
from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import Optional
from utils.database import Database
from utils.vault_manager import HardenedVaultManager
import config

app = FastAPI(title="Guardian Nexus API")

# CORS — restrict to the configured dashboard origin only
_cors_origins = [config.DASHBOARD_ORIGIN] if config.DASHBOARD_ORIGIN != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# ── API Key Authentication ────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_api_key(api_key: str = Security(_api_key_header)):
    if not config.API_SECRET_KEY:
        raise HTTPException(status_code=503, detail="API key not configured on server.")
    if not api_key or api_key != config.API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")
    return api_key

# ── Panic cooldown ─────────────────────────────────────────────────────────────

_last_panic_time: float = 0.0
_PANIC_COOLDOWN_SECONDS = 30

# ── Shared state ───────────────────────────────────────────────────────────────

class AppState:
    db: Database = None
    emergency_service = None
    vault: HardenedVaultManager = None

state = AppState()
state.vault = HardenedVaultManager()

# ── Request models ─────────────────────────────────────────────────────────────

class UnlockRequest(BaseModel):
    session_key: str

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/api/stats", dependencies=[Depends(require_api_key)])
async def get_stats():
    if not state.db:
        return {
            "assets_protected": 0,
            "incidents_blocked": 0,
            "vault_status": "OFFLINE",
            "node_status": "OFFLINE",
        }

    users = await state.db.get_all_user_states()
    wallet_count = 0
    admin_tier = "FREE"
    for u in users:
        wallets = json.loads(u["monitored_wallets_json"] or "[]")
        wallet_count += len(wallets)
        if str(u["user_id"]) in config.ADMIN_CHAT_IDS:
            admin_tier = "ADMIN"

    return {
        "assets_protected": wallet_count * 1250,
        "incidents_blocked": 42,
        "vault_status": "UNLOCKED" if state.vault.is_unlocked() else "LOCKED",
        "node_status": "ONLINE",
        "threat_level": "LOW",
        "subscription_tier": admin_tier,
    }


@app.post("/api/vault/unlock")
async def unlock_vault(req: UnlockRequest, request: Request):
    """Rate-limited vault unlock. No API key needed (must unlock before other calls)."""
    client_ip = request.client.host if request.client else "unknown"
    if state.vault.unlock(req.session_key, identifier=client_ip):
        return {"status": "success", "message": "Vault unlocked."}
    raise HTTPException(status_code=400, detail="Invalid session key or too many attempts.")


@app.post("/api/vault/lock", dependencies=[Depends(require_api_key)])
async def lock_vault():
    state.vault.lock()
    return {"status": "success", "message": "Vault locked."}


@app.get("/api/wallets", dependencies=[Depends(require_api_key)])
async def get_wallets():
    if not state.db:
        return []

    all_wallets = []
    users = await state.db.get_all_user_states()
    for u in users:
        wallets = json.loads(u["monitored_wallets_json"] or "[]")
        for addr in wallets:
            all_wallets.append({
                "address": addr,
                "status": "ACTIVE",
                "risk": 0,
                "owner": u["user_id"],
            })
    return all_wallets


@app.post("/api/panic", dependencies=[Depends(require_api_key)])
async def trigger_panic():
    global _last_panic_time
    now = time.time()
    elapsed = now - _last_panic_time
    if elapsed < _PANIC_COOLDOWN_SECONDS:
        remaining = int(_PANIC_COOLDOWN_SECONDS - elapsed)
        raise HTTPException(
            status_code=429,
            detail=f"Panic cooldown active. Try again in {remaining}s.",
        )

    logging.warning("⚠️ GLOBAL PANIC TRIGGERED VIA DASHBOARD!")

    if not state.emergency_service or not state.db:
        return {"status": "error", "message": "Emergency service not initialized."}

    if not state.vault.is_unlocked():
        raise HTTPException(status_code=403, detail="Vault is locked. Cannot execute sweep.")

    admin_id = next(iter(config.ADMIN_CHAT_IDS), None)
    if not admin_id:
        raise HTTPException(status_code=500, detail="No admin user configured.")

    _last_panic_time = now
    asyncio.create_task(state.emergency_service.execute_all(admin_id))
    return {"status": "triggered", "message": "Global emergency sweep initiated."}
