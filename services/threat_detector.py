import config

class ThreatDetector:
    def __init__(self, db=None, feature_extractor=None, pattern_matcher=None):
        self.db = db
        self.dust_threshold_sol = config.DUST_THRESHOLD_SOL
        self.dust_threshold_eth = config.DUST_THRESHOLD_ETH
        self.blacklist = set()
        self.feature_extractor = feature_extractor
        self.pattern_matcher = pattern_matcher

    async def sync_blacklist(self):
        """Syncs local blacklist cache with the database."""
        if self.db:
            addresses = await self.db.get_blacklist()
            self.blacklist.update(addresses)

    def analyze_transaction(self, tx_data):
        """
        Analyzes a transaction for suspicious patterns (Solana & EVM).
        """
        score = 0
        reasons = []

        amount = tx_data.get('amount', 0)
        sender = tx_data.get('sender', 'Unknown')
        token_name = tx_data.get('token_name', '')
        network = tx_data.get('network', 'solana')
        input_data = tx_data.get('input', '')

        # 1. Dust Detection — includes zero-amount (common in SPL-based drains)
        threshold = self.dust_threshold_sol if network == 'solana' else self.dust_threshold_eth
        if 0 <= amount < threshold:
            score += 95
            reasons.append(f"🚨 DUSTING PROBE DETECTED: {amount} {network.upper()}")

        # 2. Blacklist Check
        # EVM: case-insensitive hex. Solana: case-sensitive base58 — never lowercase.
        if network == 'solana':
            if sender in self.blacklist:
                score += 100
                reasons.append(f"Sender in blacklist: {sender}")
        else:
            if sender.lower() in {a.lower() for a in self.blacklist}:
                score += 100
                reasons.append(f"Sender in blacklist: {sender}")

        # 3. Suspicious Token Metadata
        scam_keywords = ["SCAM", "AIRDROP", "FREE", "CLAIM", "VOUCHER"]
        if any(kw in token_name.upper() for kw in scam_keywords):
            score += 60
            reasons.append(f"Suspicious token name: {token_name}")

        # 4. DeFi Approval Guard (EVM)
        # ERC20 Approve method signature: 0x095ea7b3
        if input_data.startswith('0x095ea7b3'):
            score += 50
            reasons.append("Suspicious DeFi Approval (Potential Drainer)")

        # 5. ML augmentation
        if self.feature_extractor and self.pattern_matcher:
            features = self.feature_extractor.extract(tx_data)
            ml_score = self.pattern_matcher.predict(features)
            if ml_score > 0.5:
                ml_boost = int(ml_score * 30)
                score = min(score + ml_boost, 100)
                reasons.append(f"🤖 ML Signal: {ml_score:.0%} threat probability")

        return min(score, 100), reasons

    def add_to_blacklist(self, address: str):
        self.blacklist.add(address)
