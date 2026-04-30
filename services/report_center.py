import logging

class ReportCenter:
    def __init__(self):
        self.official_channels = {
            "Chainabuse": {
                "name": "Chainabuse (Community Reporting)",
                "url": "https://www.chainabuse.com/",
                "description": "Report malicious addresses to a global database used by exchanges and investigators."
            },
            "SolanaSecurity": {
                "name": "Solana Security (X/Twitter)",
                "url": "https://x.com/SolanaSecurity",
                "description": "The official handle for reporting Solana-specific security incidents."
            },
            "PhantomSupport": {
                "name": "Phantom Support",
                "url": "https://phantom.app/help",
                "description": "Contact Phantom support for wallet-specific incident documentation."
            },
            "IC3": {
                "name": "FBI IC3 (US Residents)",
                "url": "https://www.ic3.gov/",
                "description": "Official US government portal for reporting internet-based financial crimes."
            },
            "RevokeCash": {
                "name": "Revoke.cash (Solana)",
                "url": "https://revoke.cash/s/solana",
                "description": "Revoke malicious token approvals and permissions."
            }
        }

    def get_report_summary(self):
        summary = "📢 *OFFICIAL REPORTING CHANNELS*\n\n"
        for key, info in self.official_channels.items():
            summary += f"🔹 *{info['name']}*\n"
            summary += f"🔗 [Visit Site]({info['url']})\n"
            summary += f"📝 {info['description']}\n\n"
        
        summary += "⚠️ *IMPORTANT:* Never share your seed phrase with anyone claiming to be 'support'."
        return summary

    def get_incident_form_template(self, tx_hash, wallet, risk_score):
        """Generates a template for the user to copy-paste when reporting."""
        template = (
            f"INCIDENT REPORT\n"
            f"-----------------\n"
            f"Target Wallet: {wallet}\n"
            f"Transaction Hash: {tx_hash}\n"
            f"Detected Risk: {risk_score}/100\n"
            f"Incident Type: Potential Draining/Dusting Attack\n"
            f"Bot Action: Funds Secured/Alerted\n"
            f"-----------------\n"
            f"Reported via Solana Wallet Guardian"
        )
        return template
