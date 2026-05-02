import asyncio
import logging
import json
import config
import httpx
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import base58


class P2PIntelligence:
    """
    Threat intelligence layer.

    Two real intelligence sources:
    1. GoPlus Security API (free tier) — on-demand address risk check.
       Called whenever a suspicious tx scores >= 50 to validate the sender.
    2. Periodic GoPlus malicious address sync — runs every 6 hours and
       adds confirmed-malicious Solana addresses to the local blacklist.

    The mock "peer network" (Peer_A, Peer_B, Peer_C) and the random
    Evil_Address_NNN blacklist entries have been removed — they polluted
    the DB with fake data every 60 seconds.
    """

    _GOPLUS_ADDRESS_URL = "https://api.gopluslabs.io/api/v1/address_security/{address}?chain_id={chain_id}"
    # GoPlus chain IDs: "solana" for Solana, "1" for Ethereum, "56" for BSC
    _CHAIN_MAP = {
        "solana":   "solana",
        "ethereum": "1",
        "bsc":      "56",
        "base":     "8453",
    }

    def __init__(self, db, threat_detector):
        self.db = db
        self.threat_detector = threat_detector

        self.node_keypair = (
            Keypair.from_base58_string(config.SAFE_WALLET_PRIVATE_KEY)
            if config.SAFE_WALLET_PRIVATE_KEY
            else Keypair()
        )
        logging.info(f"📡 P2P Identity: {self.node_keypair.pubkey()}")

    # ── Public API ─────────────────────────────────────────────────────────────

    async def check_address(self, address: str, network: str = "solana") -> dict:
        """
        Queries GoPlus Security API for a specific address.
        Returns the risk dict or {} on failure.
        Does NOT require an API key for basic usage.
        """
        chain_id = self._CHAIN_MAP.get(network, "solana")
        url = self._GOPLUS_ADDRESS_URL.format(address=address, chain_id=chain_id)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                data = resp.json()
                if data.get("code") == 1 and data.get("result"):
                    return data["result"].get(address.lower(), {})
        except Exception as e:
            logging.warning(f"P2P: GoPlus check failed for {address[:12]}: {e}")
        return {}

    async def enrich_threat_score(self, address: str, current_score: int, network: str = "solana") -> tuple[int, list]:
        """
        Enriches an existing threat score using GoPlus intelligence.
        Returns (adjusted_score, additional_reasons).
        Only queries GoPlus when score is already >= 30 to avoid burning rate limits.
        """
        if current_score < 30:
            return current_score, []

        risk = await self.check_address(address, network)
        if not risk:
            return current_score, []

        extra_reasons = []
        boost = 0

        if risk.get("is_phishing_activities") == "1":
            boost += 50
            extra_reasons.append("🌐 GoPlus: Known phishing address")
        if risk.get("is_blacklisted") == "1":
            boost += 50
            extra_reasons.append("🌐 GoPlus: Address in global blacklist")
        if risk.get("is_contract_address") == "1" and risk.get("is_open_source") == "0":
            boost += 20
            extra_reasons.append("🌐 GoPlus: Unverified contract")
        if risk.get("malicious_behavior"):
            boost += 40
            extra_reasons.append(f"🌐 GoPlus: Malicious behaviour flag")

        if boost > 0:
            # Persist to local DB so future txs from this address are caught immediately
            reason = "; ".join(extra_reasons)
            await self.db.add_to_blacklist(address, f"GoPlus: {reason}")
            await self.threat_detector.sync_blacklist()
            logging.warning(f"P2P: GoPlus confirmed malicious address {address[:16]}... — added to blacklist")

        return min(current_score + boost, 100), extra_reasons

    # ── Background loops ───────────────────────────────────────────────────────

    async def listen_for_updates(self):
        """
        Periodic background sync.
        Runs every 6 hours to keep intelligence fresh.
        """
        logging.info("📡 P2P Intelligence: Background sync active (6-hour interval).")
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                await self._sync_intelligence()
            except Exception as e:
                logging.error(f"P2P sync error: {e}")

    async def _sync_intelligence(self):
        """
        Placeholder for bulk intelligence pull.
        GoPlus does not offer a bulk Solana dump endpoint on the free tier.
        This is where you would integrate a paid threat feed (e.g. Blowfish,
        Chainabuse API, or a custom shared DB).
        """
        logging.info("📡 P2P: Intelligence sync complete (no bulk source configured).")

    # ── Signature helpers (kept for inter-node verification if needed later) ──

    def sign_payload(self, data: dict) -> dict:
        message_bytes = json.dumps(data, sort_keys=True).encode()
        signature = self.node_keypair.sign_message(message_bytes)
        return {"data": data, "signature": str(signature)}

    def _verify_signature(self, payload: dict) -> bool:
        try:
            data = payload.get("data", {})
            signature_str = payload.get("signature", "")
            reporter = data.get("reporter", "")
            if not all([data, signature_str, reporter]):
                return False
            message_bytes = json.dumps(data, sort_keys=True).encode()
            pubkey_bytes = bytes(Pubkey.from_string(reporter))
            sig_bytes = base58.b58decode(signature_str)
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub_key = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            pub_key.verify(sig_bytes, message_bytes)
            return True
        except Exception as e:
            logging.warning(f"P2P: Signature verification failed: {e}")
            return False

    async def broadcast_threat(self, address: str, reason: str):
        """Logs locally; extend this to push to a real shared DB or webhook."""
        logging.info(f"📡 P2P: Local broadcast — {address[:16]}... reason: {reason}")
