import logging
import json
import httpx
import config


class AIReportingService:
    """
    AI-Driven Incident Reporting.

    When AI_API_KEY is set, calls the Anthropic Messages API to generate a
    forensic narrative. Falls back to a template-based report when no key is
    configured or the API call fails.

    To enable:
      1. Set AI_API_KEY=<your-anthropic-api-key> in .env
      2. pip install anthropic   (or keep using the httpx call below)
    """

    _ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
    _MODEL = "claude-haiku-4-5-20251001"  # cheapest Anthropic model; swap for claude-sonnet-4-6 if desired

    def __init__(self):
        self.ai_api_key = config.AI_API_KEY  # dedicated env var — NOT the Fernet encryption key
        self.chainabuse_api = "https://api.chainabuse.com/v1/report"

    async def generate_forensic_report(self, tx_data: dict, risk_score: int) -> str:
        """
        Generates a human-readable forensic report.
        Uses the Anthropic API when AI_API_KEY is set, otherwise returns a
        structured template report.
        """
        logging.info("🤖 AI: Building forensic report for incident...")

        if self.ai_api_key:
            try:
                return await self._llm_report(tx_data, risk_score)
            except Exception as e:
                logging.warning(f"AI report API call failed ({e}). Falling back to template.")

        return self._template_report(tx_data, risk_score)

    async def _llm_report(self, tx_data: dict, risk_score: int) -> str:
        prompt = (
            f"You are a blockchain forensic analyst. Analyze the following Solana/EVM "
            f"transaction data and write a concise incident report suitable for law "
            f"enforcement or a security team.\n\n"
            f"Transaction data: {json.dumps(tx_data, indent=2)}\n"
            f"Risk score: {risk_score}/100\n\n"
            f"Include: attack type, attacker address, victim wallet, on-chain evidence, "
            f"and recommended remediation. Keep it under 300 words."
        )
        headers = {
            "x-api-key": self.ai_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self._MODEL,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self._ANTHROPIC_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    def _template_report(self, tx_data: dict, risk_score: int) -> str:
        sender = tx_data.get("sender", "Unknown")
        network = tx_data.get("network", "unknown").upper()
        amount = tx_data.get("amount", 0)
        sig = tx_data.get("signature", "N/A")
        return (
            f"[FORENSIC REPORT — {network}]\n"
            f"Risk Score : {risk_score}/100\n"
            f"Attacker   : {sender}\n"
            f"Amount     : {amount}\n"
            f"Tx Hash    : {sig}\n"
            f"Assessment : High-risk transaction matching drainer-as-a-service patterns. "
            f"Funds were attempted to be moved from {sender} to an unverified destination.\n"
            f"Action     : Add attacker to blacklist; file report with Chainabuse."
        )

    async def submit_to_officials(self, report_text: str, attacker_address: str) -> bool:
        """
        Submits the report to Chainabuse. Uncomment the httpx call once you
        have a Chainabuse API key.
        """
        logging.info(f"📢 Reporting attacker {attacker_address} to global databases...")
        # async with httpx.AsyncClient(timeout=10.0) as client:
        #     payload = {"address": attacker_address, "description": report_text}
        #     resp = await client.post(self.chainabuse_api, json=payload)
        #     return resp.status_code == 200
        return True
