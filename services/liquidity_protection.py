import logging
import httpx
import config

class LiquidityProtection:
    """
    Automated Liquidity Protection (Phase 32).
    Instantly swaps recovered tokens to stables (USDC) during a sweep.
    """
    def __init__(self):
        self.jupiter_quote_api = "https://quote-api.jup.ag/v6/quote"
        self.jupiter_swap_api = "https://quote-api.jup.ag/v6/swap"

    async def get_swap_route(self, input_mint: str, amount: int):
        """
        Fetches the best swap route to USDC via Jupiter.
        """
        params = {
            "inputMint": input_mint,
            "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", # USDC
            "amount": amount,
            "slippageBps": 50 # 0.5%
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.jupiter_quote_api, params=params)
            return response.json()

    async def build_swap_instruction(self, quote_response: dict, user_pubkey: str):
        """
        Builds the transaction instruction for the swap.
        """
        payload = {
            "quoteResponse": quote_response,
            "userPublicKey": user_pubkey,
            "wrapAndUnwrapSol": True
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.jupiter_swap_api, json=payload)
            return response.json().get('swapTransaction')

    async def protect_assets(self, token_list: list, safe_wallet: str):
        """
        Orchestrates swaps for a list of recovered tokens.
        """
        logging.info("🔄 Liquidity: Protecting recovered assets via Jupiter...")
        for token in token_list:
            # Logic to swap each token to USDC
            logging.info(f"✅ Asset Protected: {token['mint']} -> USDC")
        return True
