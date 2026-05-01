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
        self.peers = ["Peer_A", "Peer_B", "Peer_C"] # Simulated peer network
        
        # Node Identity (In production, this would be loaded from a secure file)
        self.node_keypair = Keypair.from_base58_string(config.SAFE_WALLET_PRIVATE_KEY) if config.SAFE_WALLET_PRIVATE_KEY else Keypair()
        logging.info(f"📡 P2P Identity: {self.node_keypair.pubkey()}")

    async def broadcast_threat(self, address: str, reason: str):
        """Broadcasts a signed threat to all connected peers."""
        data = {
            "address": address,
            "reason": reason,
            "reporter": str(self.node_keypair.pubkey()),
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Sign the message
        message_bytes = json.dumps(data, sort_keys=True).encode()
        signature = self.node_keypair.sign_message(message_bytes)
        
        payload = {
            "data": data,
            "signature": str(signature)
        }
        
        logging.info(f"📡 P2P: Broadcasting SIGNED threat {address} to {len(self.peers)} peers...")
        for peer in self.peers:
            await self._send_to_peer(peer, payload)

    async def _send_to_peer(self, peer, payload):
        await asyncio.sleep(random.uniform(0.1, 0.5))
        logging.debug(f"P2P: Sent signed payload to {peer}")

    async def listen_for_updates(self):
        """Simulates listening for threat updates from other peers."""
        logging.info("👂 P2P: Listening for network intelligence updates...")
        while True:
            await asyncio.sleep(60)
            # Simulate receiving a random signed threat
            mock_address = f"Evil_Address_{random.randint(100, 999)}"
            logging.info(f"🌐 P2P: Received community threat intelligence: {mock_address}")
            
            # In a real app, we'd verify the signature here
            # For now, we'll log it as 'Community Flagged'
            await self.db.add_to_blacklist(mock_address, "Community Flagged (Signed)")
            await self.threat_detector.sync_blacklist()
