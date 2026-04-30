import asyncio
import logging
from services.threat_detector import ThreatDetector
from services.wallet_monitor import WalletMonitor
from utils.database import Database
import config

logging.basicConfig(level=logging.INFO)

async def test_detection_logic():
    print("\n--- Testing Detection Logic ---")
    db = Database("test_guardian.db")
    await db.connect()
    
    detector = ThreatDetector(db=db)
    
    # Test 1: Dust Attack
    dust_tx = {
        "amount": 0.0001,
        "sender": "Attacker_1",
        "token_name": "SOL"
    }
    score, reasons = detector.analyze_transaction(dust_tx)
    print(f"Test 1 (Dust): Score={score}, Reasons={reasons}")
    assert score >= 40

    # Test 2: Scam Token
    scam_tx = {
        "amount": 1.0,
        "sender": "Attacker_2",
        "token_name": "FREE AIRDROP SCAM"
    }
    score, reasons = detector.analyze_transaction(scam_tx)
    print(f"Test 2 (Scam Token): Score={score}, Reasons={reasons}")
    assert score >= 60

    # Test 3: Blacklisted Sender
    await db.add_to_blacklist("Evil_Sender", "Known Spammer")
    await detector.sync_blacklist()
    blacklisted_tx = {
        "amount": 1.0,
        "sender": "Evil_Sender",
        "token_name": "SOL"
    }
    score, reasons = detector.analyze_transaction(blacklisted_tx)
    print(f"Test 3 (Blacklist): Score={score}, Reasons={reasons}")
    assert score == 100

    print("Detection Logic Tests Passed!\n")

async def test_database_logging():
    print("--- Testing Database Logging ---")
    db = Database("test_guardian.db")
    await db.connect()
    
    await db.log_threat("Wallet_A", 100, ["Test Reason"], "Test_Signature")
    
    import aiosqlite
    async with aiosqlite.connect("test_guardian.db") as conn:
        async with conn.execute("SELECT * FROM threat_logs") as cursor:
            row = await cursor.fetchone()
            print(f"Logged Threat: {row}")
            assert row is not None
    
    print("Database Logging Tests Passed!\n")

if __name__ == "__main__":
    asyncio.run(test_detection_logic())
    asyncio.run(test_database_logging())
