import asyncio
import logging
import random
import json
import config
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import base58


class P2PIntelligence:
    def __init__(self, db, threat_detector):
        self.db = db
        self.threat_detector = threat_detector
        self.peers = ["Peer_A", "Peer_B", "Peer_C"]  # Simulated peer network

        self.node_keypair = (
            Keypair.from_base58_string(config.SAFE_WALLET_PRIVATE_KEY)
            if config.SAFE_WALLET_PRIVATE_KEY
            else Keypair()
        )
        logging.info(f"📡 P2P Identity: {self.node_keypair.pubkey()}")

    async def broadcast_threat(self, address: str, reason: str):
        """Broadcasts a signed threat payload to all connected peers."""
        data = {
            "address": address,
            "reason": reason,
            "reporter": str(self.node_keypair.pubkey()),
            "timestamp": asyncio.get_event_loop().time(),
        }
        message_bytes = json.dumps(data, sort_keys=True).encode()
        signature = self.node_keypair.sign_message(message_bytes)

        payload = {"data": data, "signature": str(signature)}
        logging.info(f"📡 P2P: Broadcasting signed threat {address} to {len(self.peers)} peers...")
        for peer in self.peers:
            await self._send_to_peer(peer, payload)

    async def _send_to_peer(self, peer, payload):
        await asyncio.sleep(random.uniform(0.1, 0.5))
        logging.debug(f"P2P: Sent signed payload to {peer}")

    def _verify_signature(self, payload: dict) -> bool:
        """
        Verifies the ed25519 signature on a peer threat message.
        Returns False if the signature is missing, malformed, or invalid.
        """
        try:
            data = payload.get("data", {})
            signature_str = payload.get("signature", "")
            reporter = data.get("reporter", "")
            if not all([data, signature_str, reporter]):
                return False

            message_bytes = json.dumps(data, sort_keys=True).encode()

            # Decode Solana pubkey bytes (32-byte ed25519 public key)
            pubkey_bytes = bytes(Pubkey.from_string(reporter))
            # Decode signature bytes (64-byte ed25519 signature, base58-encoded by solders)
            sig_bytes = base58.b58decode(signature_str)

            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.exceptions import InvalidSignature
            pub_key = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            pub_key.verify(sig_bytes, message_bytes)  # raises InvalidSignature on failure
            return True
        except Exception as e:
            logging.warning(f"P2P: Signature verification failed: {e}")
            return False

    async def listen_for_updates(self):
        """Listens for threat updates from peers and verifies their signatures."""
        logging.info("👂 P2P: Listening for network intelligence updates...")
        while True:
            await asyncio.sleep(60)

            # Simulate receiving a signed threat from a peer
            mock_reporter_kp = Keypair()
            mock_address = f"Evil_Address_{random.randint(100, 999)}"
            mock_data = {
                "address": mock_address,
                "reason": "Community Flagged",
                "reporter": str(mock_reporter_kp.pubkey()),
                "timestamp": asyncio.get_event_loop().time(),
            }
            mock_message = json.dumps(mock_data, sort_keys=True).encode()
            mock_sig = mock_reporter_kp.sign_message(mock_message)
            mock_payload = {"data": mock_data, "signature": str(mock_sig)}

            if self._verify_signature(mock_payload):
                logging.info(f"🌐 P2P: Verified threat intel received: {mock_address}")
                await self.db.add_to_blacklist(mock_address, "Community Flagged (Verified Signature)")
                await self.threat_detector.sync_blacklist()
            else:
                logging.warning(f"🌐 P2P: Rejected unverified threat payload for {mock_address}")
