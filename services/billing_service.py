import asyncio
import logging
import config
from utils.database import Database

class BillingService:
    """
    Automated SaaS Billing & Tier Management.
    Monitors Treasury wallet for subscription payments.
    """
    def __init__(self, db: Database, solana_client):
        self.db = db
        self.solana_client = solana_client
        self.treasury_address = "TREASURY_ADDRESS_HERE"
        self.prices = {
            "ELITE": 20.0, # 20 USDC/mo
            "WHALE": 100.0  # 100 USDC/mo
        }

    async def start_billing_loop(self):
        """Background task to monitor for payments."""
        logging.info("💳 Billing: Starting payment monitoring loop...")
        while True:
            # In production: Fetch latest transactions for treasury_address
            # Check for USDC transfers matching prices
            # await self._process_payments()
            await asyncio.sleep(60) # Check every minute

    async def _process_payments(self, payment_data):
        """Updates user tier based on payment received."""
        user_wallet = payment_data['from']
        amount = payment_data['amount']
        
        tier = "FREE"
        if amount >= self.prices['WHALE']:
            tier = "WHALE"
        elif amount >= self.prices['ELITE']:
            tier = "ELITE"
            
        if tier != "FREE":
            logging.info(f"🎉 SUCCESS: User {user_wallet} upgraded to {tier} tier.")
            await self.db.update_user_tier(user_wallet, tier)

    async def check_access(self, user_id, feature_level):
        """Verifies if a user has access to a specific feature."""
        user_state = await self.db.get_user_state(user_id)
        current_tier = user_state[2] if user_state else "FREE"
        
        # Tier hierarchy logic
        tier_values = {"FREE": 0, "ELITE": 1, "WHALE": 2}
        return tier_values.get(current_tier, 0) >= tier_values.get(feature_level, 0)
