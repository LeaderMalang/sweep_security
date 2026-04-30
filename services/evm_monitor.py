import asyncio
import logging
from web3 import Web3, AsyncWeb3
import config

class EVMMonitor:
    def __init__(self, threat_detector, notification_service):
        self.threat_detector = threat_detector
        self.notification_service = notification_service
        self.monitored_wallets = config.EVM_WALLETS
        self.networks = config.EVM_RPC_URLS
        self.connections = {
            name: AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(url)) 
            for name, url in self.networks.items()
        }

    async def monitor(self):
        """Starts monitoring all configured EVM networks."""
        if not self.monitored_wallets:
            logging.warning("No EVM wallets configured for monitoring.")
            return

        tasks = [self._monitor_network(name, w3) for name, w3 in self.connections.items()]
        await asyncio.gather(*tasks)

    async def _monitor_network(self, name, w3):
        logging.info(f"🔗 Monitoring EVM network: {name}")
        
        # In a real app, we would use a WebSocket provider if available
        # For simplicity, we poll for new blocks
        last_block = await w3.eth.block_number
        
        while True:
            try:
                current_block = await w3.eth.block_number
                if current_block > last_block:
                    for bn in range(last_block + 1, current_block + 1):
                        block = await w3.eth.get_block(bn, full_transactions=True)
                        await self._process_block(name, block)
                    last_block = current_block
                
                await asyncio.sleep(2) # Poll every 2 seconds
            except Exception as e:
                logging.error(f"Error monitoring {name}: {e}")
                await asyncio.sleep(5)

    async def _process_block(self, network_name, block):
        for tx in block.get('transactions', []):
            to_address = tx.get('to')
            if to_address and to_address.lower() in [w.lower() for w in self.monitored_wallets]:
                await self._handle_evm_transaction(network_name, tx)

    async def _handle_evm_transaction(self, network, tx):
        signature = tx['hash'].hex()
        value_eth = Web3.from_wei(tx['value'], 'ether')
        sender = tx['from']
        
        logging.info(f"⚡ {network.upper()} Transaction detected: {signature}")
        
        # Analyze with Threat Detector
        tx_data = {
            "amount": float(value_eth),
            "sender": sender,
            "network": network,
            "signature": signature
        }
        
        score, reasons = self.threat_detector.analyze_transaction(tx_data)
        
        if score >= config.RISK_SCORE_THRESHOLD:
            await self.notification_service.send_threat_alert(
                wallet_address=tx['to'],
                score=score,
                reasons=reasons,
                tx_hash=f"{network}:{signature}"
            )
