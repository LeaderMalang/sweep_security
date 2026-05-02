import aiosqlite
import json
import logging

import os

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", "guardian.db")

    async def connect(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Threat Logs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS threat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT,
                    risk_score INTEGER,
                    reasons TEXT,
                    signature TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Blacklist
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    address TEXT PRIMARY KEY,
                    reason TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Whitelist (Trusted Addresses)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    address TEXT PRIMARY KEY,
                    label TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # User state for hygiene and SaaS tiers
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_state (
                    user_id TEXT PRIMARY KEY,
                    auto_defense BOOLEAN DEFAULT FALSE,
                    tier TEXT DEFAULT "FREE",
                    subscription_tier TEXT DEFAULT "FREE",
                    last_daily_check TEXT,
                    last_weekly_audit TEXT,
                    hardware_wallet BOOLEAN DEFAULT FALSE,
                    safe_wallet_configured BOOLEAN DEFAULT FALSE,
                    safe_wallet_address TEXT,
                    monitored_wallets_json TEXT DEFAULT '[]',
                    skimming_enabled BOOLEAN DEFAULT FALSE,
                    skimming_threshold REAL DEFAULT 0.02,
                    skimming_retain REAL DEFAULT 0.01,
                    custom_rpc_url TEXT,
                    bait_wallets_json TEXT DEFAULT '[]',
                    subscription_expiry DATETIME,
                    rpc_usage_count INTEGER DEFAULT 0
                )
            ''')
            # Database Migrations (Add missing columns to existing DB)
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN subscription_tier TEXT DEFAULT 'free'")
            except Exception: pass # Already exists
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN subscription_expiry DATETIME")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN rpc_usage_count INTEGER DEFAULT 0")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN bait_wallets_json TEXT DEFAULT '[]'")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN jito_tip_sol FLOAT DEFAULT 0.001")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN auto_refill_gas BOOLEAN DEFAULT 1")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN daily_sweep_enabled BOOLEAN DEFAULT FALSE")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN daily_sweep_time TEXT DEFAULT '00:00'")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN smart_thresholds_enabled BOOLEAN DEFAULT FALSE")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN nonce_account TEXT")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN daily_report_enabled BOOLEAN DEFAULT FALSE")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE user_state ADD COLUMN daily_report_time TEXT DEFAULT '08:00'")
            except Exception: pass

            await db.commit()
            await db.execute("""
                CREATE TABLE IF NOT EXISTS wallet_vault (
                    wallet_address TEXT PRIMARY KEY,
                    encrypted_privkey TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logging.info("Database initialized with Phase 7 State Tracking + Vault.")

    async def store_vault_key(self, address, encrypted_key):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO wallet_vault (wallet_address, encrypted_privkey) VALUES (?, ?)",
                (address, encrypted_key)
            )
            await db.commit()

    async def get_vault_key(self, address):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT encrypted_privkey FROM wallet_vault WHERE wallet_address = ?", (address,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def delete_vault_key(self, address):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM wallet_vault WHERE wallet_address = ?", (address,))
            await db.commit()

    async def increment_rpc_usage(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_state SET rpc_usage_count = rpc_usage_count + 1 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()

    async def update_user_tier(self, user_id, tier):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_state SET tier = ? WHERE user_id = ?",
                (tier, user_id)
            )
            await db.commit()

    async def update_user_state(self, user_id, **kwargs):
        """Updates specific fields in the user security state."""
        async with aiosqlite.connect(self.db_path) as db:
            cols = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            vals = list(kwargs.values()) + [user_id]
            await db.execute(f"UPDATE user_state SET {cols} WHERE user_id = ?", vals)
            # Insert if not exists
            await db.execute(f"INSERT OR IGNORE INTO user_state (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def get_user_state(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row # <--- Added this line
            async with db.execute("SELECT * FROM user_state WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()

    async def get_all_user_states(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM user_state") as cursor:
                return await cursor.fetchall()


    async def log_threat(self, wallet, score, reasons, signature):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO threat_logs (wallet_address, risk_score, reasons, signature) VALUES (?, ?, ?, ?)",
                (wallet, score, ",".join(reasons), signature)
            )
            await db.commit()

    async def add_to_blacklist(self, address, reason):
        # Lowercase EVM addresses; preserve Solana case sensitivity
        normalized = address.lower() if address.startswith('0x') else address.strip()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO blacklist (address, reason) VALUES (?, ?)",
                (normalized, reason)
            )
            await db.commit()

    async def add_to_whitelist(self, address, label="Trusted"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO whitelist (address, label) VALUES (?, ?)",
                (address, label)
            )
            await db.commit()

    async def get_whitelist(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT address FROM whitelist") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_history(self, limit=5, wallet_addresses=None):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if wallet_addresses:
                placeholders = ",".join("?" * len(wallet_addresses))
                query = f"SELECT * FROM threat_logs WHERE wallet_address IN ({placeholders}) ORDER BY timestamp DESC LIMIT ?"
                async with db.execute(query, wallet_addresses + [limit]) as cursor:
                    return await cursor.fetchall()
            async with db.execute("SELECT * FROM threat_logs ORDER BY timestamp DESC LIMIT ?", (limit,)) as cursor:
                return await cursor.fetchall()

    async def get_blacklist(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT address FROM blacklist") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
