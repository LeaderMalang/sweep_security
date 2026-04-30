import logging

class TransactionFeatureExtractor:
    def extract(self, tx_data):
        """
        Extracts numerical features from transaction data for ML models.
        """
        features = {
            "amount_sol": tx_data.get("amount", 0),
            "is_spl_token": 1 if tx_data.get("token_address") else 0,
            "sender_reputation": 0, # Placeholder for history lookup
            "instruction_count": len(tx_data.get("instructions", [])),
            "metadata_risk": self._calculate_metadata_risk(tx_data.get("token_name", ""))
        }
        return features

    def _calculate_metadata_risk(self, token_name):
        scam_keywords = ["SCAM", "FREE", "AIRDROP", "VOUCHER", "CLAIM"]
        if any(kw in token_name.upper() for kw in scam_keywords):
            return 1.0
        return 0.0

class PatternMatcher:
    def __init__(self):
        # In a real app, this would be a loaded scikit-learn model
        self.model = None

    def predict(self, features):
        """
        Predicts if a transaction is an attack based on extracted features.
        Returns a probability score (0.0 - 1.0).
        """
        # Simulated heuristic model for Phase 4
        score = 0.0
        if features["amount_sol"] < 0.001: score += 0.4
        if features["metadata_risk"] > 0.5: score += 0.5
        if features["instruction_count"] > 5: score += 0.2
        
        return min(score, 1.0)
