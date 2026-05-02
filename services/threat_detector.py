import logging
import config

# SPL token programs — presence means tokens are being moved/approved
_TOKEN_PROGRAMS = {
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbEquAZkGfyQ3VaHHMGKKCJRFnxPgGHCCBW",
}

# Programs that have no reason to appear in a routine user-initiated transaction.
# Draining services use these to atomically drain SOL + all SPL tokens in one tx.
# Add to this set as new drainer programs are discovered.
_KNOWN_DRAINER_PROGRAMS = {
    "DrainS5AAKL9PgVA9HLkq7fdGv3i3LVRmJkpFBwDcbJe",  # Example — replace with real discovered IDs
}


class ThreatDetector:
    def __init__(self, db=None, feature_extractor=None, pattern_matcher=None):
        self.db = db
        self.dust_threshold_sol = config.DUST_THRESHOLD_SOL
        self.dust_threshold_eth = config.DUST_THRESHOLD_ETH
        self.blacklist: set = set()
        self.drainer_programs: set = set(_KNOWN_DRAINER_PROGRAMS)
        self.feature_extractor = feature_extractor
        self.pattern_matcher = pattern_matcher

    async def sync_blacklist(self):
        """Syncs local blacklist cache with the database."""
        if self.db:
            addresses = await self.db.get_blacklist()
            self.blacklist.update(addresses)

    def analyze_transaction(self, tx_data: dict) -> tuple[int, list]:
        """
        Analyzes a transaction for suspicious patterns (Solana & EVM).
        Returns (risk_score 0–100, list of reason strings).
        """
        score = 0
        reasons = []

        amount        = tx_data.get("amount", 0)
        sender        = tx_data.get("sender", "Unknown")
        token_name    = tx_data.get("token_name", "")
        network       = tx_data.get("network", "solana")
        input_data    = tx_data.get("input", "")
        program_ids   = set(tx_data.get("program_ids", []))
        ix_count      = tx_data.get("instruction_count", 0)
        inner_count   = tx_data.get("inner_instruction_count", 0)
        is_spl        = tx_data.get("is_spl_token", False)

        threshold = self.dust_threshold_sol if network == "solana" else self.dust_threshold_eth

        # ── 1. Dust / zero-amount probe ────────────────────────────────────────
        # Includes amount == 0 (common in SPL-only drains that send 0 SOL)
        if 0 <= amount < threshold:
            score += 95
            reasons.append(f"🚨 DUSTING PROBE: {amount} {network.upper()}")

        # ── 2. Blacklist sender ────────────────────────────────────────────────
        # EVM: case-insensitive. Solana: exact case (base58 is case-sensitive).
        if network == "solana":
            if sender in self.blacklist:
                score += 100
                reasons.append(f"🚨 BLACKLISTED SENDER: {sender[:16]}...")
        else:
            if sender.lower() in {a.lower() for a in self.blacklist}:
                score += 100
                reasons.append(f"🚨 BLACKLISTED SENDER: {sender}")

        # ── 3. Scam token metadata ────────────────────────────────────────────
        _SCAM_KEYWORDS = {"SCAM", "AIRDROP", "FREE", "CLAIM", "VOUCHER", "REWARD", "BONUS"}
        if any(kw in token_name.upper() for kw in _SCAM_KEYWORDS):
            score += 60
            reasons.append(f"⚠️ SUSPICIOUS TOKEN NAME: {token_name}")

        # ── 4. EVM: ERC20 unlimited approval (drainer signature) ──────────────
        if input_data.startswith("0x095ea7b3"):
            score += 50
            reasons.append("⚠️ ERC20 UNLIMITED APPROVAL — potential drainer")

        # ── 5. High instruction count (Solana-specific) ────────────────────────
        # Legitimate SOL transfers use 1-2 instructions.
        # Drainers batch: sweep SOL + close all token accounts + transfer all tokens.
        total_ix = ix_count + inner_count
        if total_ix >= 10:
            score += 50
            reasons.append(f"🚨 VERY HIGH INSTRUCTION COUNT: {total_ix} (drainer pattern)")
        elif total_ix >= 6:
            score += 25
            reasons.append(f"⚠️ ELEVATED INSTRUCTION COUNT: {total_ix}")

        # ── 6. SPL token program + dust SOL (classic drainer combo) ──────────
        # A tx that moves near-zero SOL but invokes Token Program is the
        # canonical drainer-as-a-service pattern (Inferno, Pink drainer, etc.)
        if is_spl and 0 <= amount < threshold:
            score += 35
            reasons.append("🚨 SPL TOKEN TRANSFER WITH DUST SOL — classic drainer signature")

        # ── 7. SPL token with high instruction count ──────────────────────────
        if is_spl and total_ix >= 6:
            score += 20
            reasons.append("⚠️ Token program + high instruction count")

        # ── 8. Known drainer program ID ───────────────────────────────────────
        bad = program_ids & self.drainer_programs
        if bad:
            score += 100
            reasons.append(f"🚨 KNOWN DRAINER PROGRAM: {', '.join(list(bad)[:2])}")

        # ── 9. ML augmentation ────────────────────────────────────────────────
        if self.feature_extractor and self.pattern_matcher:
            features = self.feature_extractor.extract(tx_data)
            ml_score = self.pattern_matcher.predict(features)
            if ml_score > 0.5:
                boost = int(ml_score * 30)
                score = min(score + boost, 100)
                reasons.append(f"🤖 ML SIGNAL: {ml_score:.0%} threat probability")

        return min(score, 100), reasons

    def add_to_blacklist(self, address: str):
        self.blacklist.add(address)

    def add_drainer_program(self, program_id: str):
        self.drainer_programs.add(program_id)
