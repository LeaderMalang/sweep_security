import logging


class TransactionFeatureExtractor:
    """
    Extracts numerical features from transaction data for the pattern matcher.
    All features are normalized to [0, 1] or meaningful numeric ranges.
    """

    _SCAM_KEYWORDS = {"SCAM", "FREE", "AIRDROP", "VOUCHER", "CLAIM", "REWARD", "BONUS"}

    def extract(self, tx_data: dict) -> dict:
        amount        = float(tx_data.get("amount", 0))
        ix_count      = int(tx_data.get("instruction_count", 0))
        inner_count   = int(tx_data.get("inner_instruction_count", 0))
        is_spl        = 1 if tx_data.get("is_spl_token") else 0
        token_name    = tx_data.get("token_name", "")
        reputation    = float(tx_data.get("sender_reputation", 0))  # 0 = unknown, -1 = bad, +1 = trusted
        program_risk  = 1.0 if tx_data.get("has_drainer_program") else 0.0

        return {
            "amount_sol":             amount,
            "is_spl_token":           is_spl,
            "sender_reputation":      reputation,
            "instruction_count":      ix_count,
            "inner_instruction_count": inner_count,
            "total_instruction_count": ix_count + inner_count,
            "metadata_risk":          self._metadata_risk(token_name),
            "program_risk":           program_risk,
            # Composite feature: dust SOL + SPL involvement (canonical drainer combo)
            "dust_spl_combo":         1 if (amount < 0.0001 and is_spl) else 0,
        }

    def _metadata_risk(self, token_name: str) -> float:
        if any(kw in token_name.upper() for kw in self._SCAM_KEYWORDS):
            return 1.0
        return 0.0


class PatternMatcher:
    """
    Heuristic rule-based pattern matcher.

    Scoring:
      - Each rule adds a weight between 0.0 and 1.0.
      - Final score is clipped to [0.0, 1.0].
      - Scores > 0.5 are treated as a positive threat signal by ThreatDetector.

    To replace with a real trained model:
      1. Collect labelled tx_data dicts (attack=1, benign=0).
      2. Call TransactionFeatureExtractor().extract() on each.
      3. Train sklearn RandomForestClassifier or XGBoostClassifier.
      4. Serialize with joblib.dump(clf, 'model.joblib').
      5. In __init__: self.model = joblib.load('model.joblib')
      6. In predict: return float(self.model.predict_proba([list(features.values())])[0][1])
    """

    def __init__(self, model_path: str = None):
        self.model = None
        if model_path:
            try:
                import joblib
                self.model = joblib.load(model_path)
                logging.info(f"🤖 ML Model loaded from {model_path}")
            except Exception as e:
                logging.warning(f"ML model load failed ({e}); falling back to heuristic rules.")

    def predict(self, features: dict) -> float:
        """Returns threat probability [0.0, 1.0]."""
        if self.model is not None:
            try:
                feature_vector = [
                    features["amount_sol"],
                    features["is_spl_token"],
                    features["sender_reputation"],
                    features["instruction_count"],
                    features["inner_instruction_count"],
                    features["total_instruction_count"],
                    features["metadata_risk"],
                    features["program_risk"],
                    features["dust_spl_combo"],
                ]
                return float(self.model.predict_proba([feature_vector])[0][1])
            except Exception as e:
                logging.warning(f"ML inference failed: {e}. Falling back to rules.")

        return self._heuristic(features)

    def _heuristic(self, f: dict) -> float:
        score = 0.0

        # Small SOL amount — common in both dust attacks and innocent micro-transfers
        if f["amount_sol"] < 0.001:
            score += 0.35

        # Dust + SPL token: canonical drainer-as-a-service pattern
        if f["dust_spl_combo"]:
            score += 0.55

        # High instruction count
        total = f["total_instruction_count"]
        if total >= 10:
            score += 0.50
        elif total >= 6:
            score += 0.25

        # Scam token metadata
        if f["metadata_risk"] > 0.5:
            score += 0.50

        # Known bad sender reputation
        if f["sender_reputation"] < 0:
            score += 0.60

        # Known drainer program
        if f["program_risk"] > 0.5:
            score += 0.90

        return min(score, 1.0)
