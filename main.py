import asyncio
import logging
import signal
import config
from services.wallet_monitor import WalletMonitor
from services.evm_monitor import EVMMonitor
from services.threat_detector import ThreatDetector
from services.notification_service import NotificationService
from services.emergency_transfer import EmergencyTransfer
from services.honey_pot_manager import HoneyPotManager
from services.advanced_recovery import AdvancedRecovery
from services.ml_detector import TransactionFeatureExtractor, PatternMatcher
from services.p2p_intelligence import P2PIntelligence
from services.hygiene_manager import HygieneManager
from services.gas_tank_manager import GasTankManager
from services.pre_signed_service import PreSignedService
from services.mempool_watcher import MempoolWatcher
from services.bridge_service import BridgeService
from services.ai_reporting_service import AIReportingService
from services.federated_mesh import FederatedSecurityMesh
from services.liquidity_protection import LiquidityProtection
from utils.solana_client import SolanaClient
from utils.database import Database
from utils.jito_client import JitoClient
from utils.vault_manager import HardenedVaultManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main():
    logging.info("🌌 Starting Guardian Nexus ULTRA-FRONTIER (v2.0-Omega)...")

    # ── Core Infrastructure ────────────────────────────────────────────────────
    db = Database()
    await db.connect()
    solana_client = SolanaClient(db=db)
    jito_client = JitoClient()
    vault = HardenedVaultManager()

    # ── Defence & Recovery Layer ───────────────────────────────────────────────
    pre_signed_service = PreSignedService(solana_client)
    mempool_watcher = MempoolWatcher(None, None, pre_signed_service, db=db)
    bridge_service = BridgeService()
    liquidity_guard = LiquidityProtection()
    ai_reporting = AIReportingService()

    # ── Intelligence Layer ─────────────────────────────────────────────────────
    feature_extractor = TransactionFeatureExtractor()
    pattern_matcher = PatternMatcher()
    threat_detector = ThreatDetector(db=db, feature_extractor=feature_extractor, pattern_matcher=pattern_matcher)
    p2p_network = P2PIntelligence(db=db, threat_detector=threat_detector)
    federated_mesh = FederatedSecurityMesh(db=db)

    # ── Governance & Readiness ─────────────────────────────────────────────────
    notification_service = NotificationService(db=db)
    mempool_watcher.threat_detector = threat_detector
    mempool_watcher.notification_service = notification_service
    hygiene_manager = HygieneManager(db=db, notification_service=notification_service)
    gas_tank = GasTankManager(solana_client)

    # ── Response Engine ────────────────────────────────────────────────────────
    emergency_service = EmergencyTransfer(solana_client, jito_client=jito_client, db=db)
    notification_service.emergency_service = emergency_service
    emergency_service.notification_service = notification_service
    wallet_monitor = WalletMonitor(threat_detector, notification_service, db, emergency_service)
    evm_monitor = EVMMonitor(threat_detector, notification_service)
    honey_pot_manager = HoneyPotManager(db=db, threat_detector=threat_detector, emergency_service=emergency_service)
    notification_service.honey_pot_manager = honey_pot_manager

    # ── API Bridge ─────────────────────────────────────────────────────────────
    from api.server import app, state as api_state
    import uvicorn
    api_state.db = db
    api_state.emergency_service = emergency_service

    api_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    api_server = uvicorn.Server(api_config)

    # ── Graceful Shutdown ──────────────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _request_stop():
        logging.info("🛑 Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            pass  # Windows fallback — KeyboardInterrupt handles it

    all_coroutines = [
        api_server.serve(),
        wallet_monitor.monitor(),
        evm_monitor.monitor(),
        honey_pot_manager.start_monitoring(),
        honey_pot_manager.run_skimmer(),
        honey_pot_manager.run_daily_harvest(),
        p2p_network.listen_for_updates(),
        hygiene_manager.start_hygiene_loops(),
        gas_tank.monitor_gas_levels([config.SAFE_WALLET_ADDRESS]),
        mempool_watcher.start_solana_mempool(),
        federated_mesh.fetch_global_immune_signatures(),
        notification_service.start(),
    ]

    tasks = [asyncio.create_task(coro) for coro in all_coroutines]

    logging.info("🛡️ GUARDIAN NEXUS ULTRA-FRONTIER ONLINE 🛡️")

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Shutting down Guardian Nexus gracefully...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await solana_client.close()
        logging.info("✅ Guardian Nexus stopped.")


if __name__ == "__main__":
    asyncio.run(main())
