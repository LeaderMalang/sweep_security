# 🛡️ Guardian Nexus: Ultra-Frontier (v2.0)

Guardian Nexus is a sub-millisecond security sentinel designed to protect Solana and EVM assets from high-speed drainers. It utilizes Jito Bundles, Durable Nonces, and a Hardened Database Vault to ensure assets are rescued before attackers can confirm their transactions.

## 🚀 Key Hardening Features (Phase 1 Complete)
- **⚡ Latency Hardening**: Support for **Durable Nonces**, allowing pre-signed recovery transactions that never expire.
- **🔒 Storage Hardening**: Refactored **HardenedVaultManager** with AES-256 encryption and SQLite persistence. Keys are session-locked and only accessible via a transient session key.
- **📡 Network Hardening**: **Cryptographic P2P Intelligence** signing. Threat data is now signed with node identities to prevent network poisoning.
- **🍯 Honey Pot Skimming**: Automated harvesting of profit from attackers sending "bait" gas to monitored wallets.

## 🤖 Telegram Bot Interface
The Telegram bot is the primary control center for the Guardian Nexus.

### Core Commands
- `/start`: Open the Security Dashboard and initialize the setup wizard.
- `/status`: Detailed overview of all monitored wallets, gas levels, and protection status.
- `/panic`: **Global Emergency Sweep**. Instantly moves all protected assets to your Safe Wallet.
- `/vault`: Guided wizard to securely encrypt and store private keys.
- `/settings`: Interactive menu to toggle Auto-Defense, Skimming, and Daily Harvests.
- `/unlock [key]`: Unlock the hardened vault session for the current runtime.
- `/setup_nonce`: Create and fund a Durable Nonce account for zero-latency rescue.

### Tactical Commands
- `/set_tip [sol]`: Adjust Jito validator tips (Recommended: 0.005 SOL).
- `/set_rpc [url]`: Link your account to a private high-speed RPC node.
- `/add_monitored`: Add a new wallet to the active watch-list.
- `/skim [retain] [trigger]`: Configure the "Harvest" logic for bait wallets.
- `/health`: Real-time system health check (RPC, Mesh, Database).

## 🛠️ Architecture
- **Language**: Python 3.10+ (Asyncio)
- **Database**: SQLite (Aiosqlite)
- **Provider**: Solana ATN (Authenticated Transaction Network)
- **Encryption**: Fernet (AES-128/256)
- **Mempool**: Jito Shredstream / Helius Webhooks

## 🛡️ Security Protocol
1. **Friendly Fire Prevention**: Automatic whitelisting of your own transactions and the Global Safe Wallet.
2. **Session Isolation**: Decrypted keys exist only in volatile memory during an active session.
3. **Multi-Node Gossip**: Threat intelligence is verified across a federated mesh of Guardian nodes.

---
*Developed for Guardian Nexus Infrastructure. 2026.*
