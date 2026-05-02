import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Solana Configuration
rpc_env = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
SOLANA_RPC_URLS = [url.strip() for url in rpc_env.split(",") if url.strip()]
SOLANA_WSS_URL = os.getenv("SOLANA_WSS_URL", "wss://api.mainnet-beta.solana.com")
SHREDSTREAM_URL = os.getenv("SHREDSTREAM_URL", "")

# EVM Configuration (Ethereum, BSC, Base)
EVM_RPC_URLS = {
    "ethereum": os.getenv("ETH_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/your-api-key"),
    "bsc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
    "base": os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
}

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Multi-Admin Support: ADMIN_CHAT_IDS is a comma-separated list of admin Telegram user IDs.
# Falls back to TELEGRAM_CHAT_ID for single-admin setups.
_admin_ids_raw = os.getenv("ADMIN_CHAT_IDS", TELEGRAM_CHAT_ID or "")
ADMIN_CHAT_IDS: set = {aid.strip() for aid in _admin_ids_raw.split(",") if aid.strip()}

# Security Configuration
SAFE_WALLET_ADDRESS = os.getenv("SAFE_WALLET_ADDRESS")
SAFE_WALLET_PRIVATE_KEY = os.getenv("SAFE_WALLET_PRIVATE_KEY")
EVM_SAFE_ADDRESS = os.getenv("EVM_SAFE_ADDRESS")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# API Security — must be set in production; dashboard requests must include X-API-Key header
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

# Dashboard CORS origin — restrict to the actual dashboard URL in production
DASHBOARD_ORIGIN = os.getenv("DASHBOARD_ORIGIN", "http://localhost:3000")

# Thresholds
DUST_THRESHOLD_SOL = float(os.getenv("DUST_THRESHOLD_SOL", "0.0001"))
DUST_THRESHOLD_ETH = float(os.getenv("DUST_THRESHOLD_ETH", "0.0001"))
RISK_SCORE_THRESHOLD = int(os.getenv("RISK_SCORE_THRESHOLD", "50"))

# Monitoring
MONITORED_WALLETS = os.getenv("MONITORED_WALLETS", "").split(",")
MONITORED_WALLETS = [w.strip() for w in MONITORED_WALLETS if w.strip()]

EVM_WALLETS = os.getenv("EVM_WALLETS", "").split(",")
EVM_WALLETS = [w.strip() for w in EVM_WALLETS if w.strip()]

# Startup validation — warn about missing critical variables
_REQUIRED_VARS = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "SAFE_WALLET_ADDRESS": SAFE_WALLET_ADDRESS,
    "ENCRYPTION_KEY": ENCRYPTION_KEY,
}
_missing = [k for k, v in _REQUIRED_VARS.items() if not v]
if _missing:
    logging.warning(f"⚠️  Missing critical environment variables: {_missing}. Some features will be disabled.")

if not API_SECRET_KEY:
    logging.warning("⚠️  API_SECRET_KEY is not set. The REST API is unprotected. Set API_SECRET_KEY in .env.")
