from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import logging
from utils.database import Database
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

state = AppState()

class WalletRequest(BaseModel):
    address: str
    label: Optional[str] = "Primary"

@app.get("/api/stats")
async def get_stats():
    return {
        "assets_protected": 248500,
        "incidents_blocked": 1492,
        "vault_status": "LOCKED",
        "node_status": "ONLINE",
        "threat_level": "LOW"
    }

@app.get("/api/wallets")
async def get_wallets():
    if not state.db:
        return []
    # In production, query the DB
    return [{"address": "7xKX...2p1", "status": "ACTIVE", "risk": 5}]

@app.post("/api/panic")
async def trigger_panic():
    logging.warning("⚠️ GLOBAL PANIC TRIGGERED VIA DASHBOARD!")
    if state.emergency_service:
        # Trigger actual recovery logic
        # asyncio.create_task(state.emergency_service.execute_all())
        pass
    return {"status": "triggered", "message": "Emergency sweep initiated."}
