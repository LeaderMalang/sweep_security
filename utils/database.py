import aiosqlite
import json
import logging

class Database:
    def __init__(self, db_path="guardian.db"):
        self.db_path = db_path

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
                    custom_rpc_url TEXT
                )
            ''')
            # Secure Wallet Vault
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


    async def log_threat(self, wallet, score, reasons, signature):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO threat_logs (wallet_address, risk_score, reasons, signature) VALUES (?, ?, ?, ?)",
                (wallet, score, ",".join(reasons), signature)
            )
            await db.commit()

    async def add_to_blacklist(self, address, reason):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO blacklist (address, reason) VALUES (?, ?)",
                (address.lower(), reason)
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

    async def get_history(self, limit=5):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM threat_logs ORDER BY timestamp DESC LIMIT ?", (limit,)) as cursor:
                return await cursor.fetchall()

    async def get_blacklist(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT address FROM blacklist") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
