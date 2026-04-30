import asyncio
import logging
import random
import config

class P2PIntelligence:
    def __init__(self, db, threat_detector):
        self.db = db
        self.threat_detector = threat_detector
        self.peers = ["Peer_A", "Peer_B", "Peer_C"] # Simulated peer network

    async def broadcast_threat(self, address: str, reason: str):
        """Broadcasts a new threat to all connected peers."""
        logging.info(f"📡 P2P: Broadcasting threat {address} to {len(self.peers)} peers...")
        # In a real implementation, this would use a transport layer like libp2p
        for peer in self.peers:
            await self._send_to_peer(peer, address, reason)

    async def _send_to_peer(self, peer, address, reason):
        # Simulated network latency
        await asyncio.sleep(random.uniform(0.1, 0.5))
        logging.debug(f"P2P: Sent threat data to {peer}")

    async def listen_for_updates(self):
        """Simulates listening for threat updates from other peers."""
        logging.info("👂 P2P: Listening for network intelligence updates...")
        while True:
            # Simulate receiving a random threat from the network every 60 seconds
            await asyncio.sleep(60)
            incoming_threat = f"Evil_Peer_Address_{random.randint(100, 999)}"
            logging.info(f"🌐 P2P: Received community threat intelligence: {incoming_threat}")
            
            await self.db.add_to_blacklist(incoming_threat, "Community Flagged")
            await self.threat_detector.sync_blacklist()
