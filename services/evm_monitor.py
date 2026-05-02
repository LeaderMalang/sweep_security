import asyncio
import logging
from web3 import Web3, AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware
import config

# Networks that use PoA / non-standard extraData (Parlia, Clique, etc.)
_POA_NETWORKS = {"bsc", "polygon", "base"}

class EVMMonitor:
    def __init__(self, threat_detector, notification_service, db=None):
        self.threat_detector = threat_detector
        self.notification_service = notification_service
        self.db = db
        self.monitored_wallets = config.EVM_WALLETS
        self.networks = config.EVM_RPC_URLS
        self.connections = {}
        for name, url in self.networks.items():
            w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(url))
            if name.lower() in _POA_NETWORKS:
                w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            self.connections[name] = w3
        # wallet → user_id mapping, populated from DB on start
        self.wallet_to_user: dict = {}

    async def monitor(self):
        """Starts monitoring all configured EVM networks."""
        if not self.monitored_wallets and not self.db:
            logging.warning("No EVM wallets configured for monitoring.")
            return

        if self.db:
            await self._refresh_wallet_map()

        tasks = [self._monitor_network(name, w3) for name, w3 in self.connections.items()]
        await asyncio.gather(*tasks)

    async def _refresh_wallet_map(self):
        """Builds wallet→user_id map from the database."""
        import json
        users = await self.db.get_all_user_states()
        self.wallet_to_user = {}
        for row in users:
            user = dict(row)
            uid = str(user["user_id"])
            for w in json.loads(user.get("monitored_wallets_json", "[]") or "[]"):
                self.wallet_to_user[w.lower()] = uid

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
        all_wallets = set(w.lower() for w in self.monitored_wallets)
        all_wallets.update(self.wallet_to_user.keys())
        for tx in block.get('transactions', []):
            to_address = tx.get('to')
            if to_address and to_address.lower() in all_wallets:
                await self._handle_evm_transaction(network_name, tx)

    async def _handle_evm_transaction(self, network, tx):
        signature = tx['hash'].hex()
        value_eth = Web3.from_wei(tx['value'], 'ether')
        sender = tx['from']
        to_addr = tx.get('to', '')
        input_data = (tx.get('input') or tx.get('data') or b'')
        if isinstance(input_data, bytes):
            input_data = '0x' + input_data.hex()

        logging.info(f"⚡ {network.upper()} Transaction detected: {signature}")

        tx_data = {
            "amount": float(value_eth),
            "sender": sender,
            "network": network,
            "signature": signature,
            "input": input_data,        # needed for ERC20 approval detection
            "token_name": "",           # EVM tx metadata not available at this layer
            "instruction_count": 0,
            "inner_instruction_count": 0,
            "is_spl_token": False,
            "program_ids": [],
        }

        score, reasons = self.threat_detector.analyze_transaction(tx_data)

        if score >= config.RISK_SCORE_THRESHOLD:
            user_id = self.wallet_to_user.get(to_addr.lower() if to_addr else "")
            await self.notification_service.send_threat_alert(
                wallet_address=to_addr,
                score=score,
                reasons=reasons,
                tx_hash=f"{network}:{signature}",
                user_id=user_id,
            )
