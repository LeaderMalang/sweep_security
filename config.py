import os
from dotenv import load_dotenv

load_dotenv()

# Solana Configuration
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
SOLANA_WSS_URL = os.getenv("SOLANA_WSS_URL", "wss://api.devnet.solana.com")

# EVM Configuration (Ethereum, BSC, Base)
EVM_RPC_URLS = {
    "ethereum": os.getenv("ETH_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/your-api-key"),
    "bsc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
    "base": os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
}

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Security Configuration
SAFE_WALLET_ADDRESS = os.getenv("SAFE_WALLET_ADDRESS")
SAFE_WALLET_PRIVATE_KEY = os.getenv("SAFE_WALLET_PRIVATE_KEY")
EVM_SAFE_ADDRESS = os.getenv("EVM_SAFE_ADDRESS")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Thresholds
DUST_THRESHOLD_SOL = float(os.getenv("DUST_THRESHOLD_SOL", "0.001"))
DUST_THRESHOLD_ETH = float(os.getenv("DUST_THRESHOLD_ETH", "0.0001"))
RISK_SCORE_THRESHOLD = int(os.getenv("RISK_SCORE_THRESHOLD", "50"))

# Monitoring
MONITORED_WALLETS = os.getenv("MONITORED_WALLETS", "").split(",")
MONITORED_WALLETS = [w.strip() for w in MONITORED_WALLETS if w.strip()]

EVM_WALLETS = os.getenv("EVM_WALLETS", "").split(",")
EVM_WALLETS = [w.strip() for w in EVM_WALLETS if w.strip()]
