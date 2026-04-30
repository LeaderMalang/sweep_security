from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
import config
import logging
import json

class NotificationService:
    def __init__(self, db=None, emergency_service=None):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.db = db
        self.emergency_service = emergency_service
        self._register_handlers()

    def _register_handlers(self):
        @self.dp.callback_query(F.data.startswith("sweep_"))
        async def handle_manual_sweep_callback(callback: types.CallbackQuery):
            wallet = callback.data.split("_")[1]
            await callback.message.answer(f"🚀 Executing Emergency Sweep for {wallet}...")
            if self.emergency_service:
                await self.emergency_service.sweep_all(wallet, config.SAFE_WALLET_ADDRESS)
            await callback.answer("Sweep Initiated")

        @self.dp.callback_query(F.data == "toggle_auto")
        async def handle_toggle_auto(callback: types.CallbackQuery):
            user_id = str(callback.from_user.id)
            state = await self.db.get_user_state(user_id)
            current = state['auto_defense'] if state else False
            await self.db.update_user_state(user_id, auto_defense=not current)
            new_status = "ON" if not current else "OFF"
            await callback.message.edit_text(f"🤖 Auto-Defense is now: *{new_status}*", parse_mode="Markdown")
            await callback.answer(f"Auto-Defense {new_status}")

        @self.dp.callback_query(F.data == "change_safe")
        async def handle_change_safe(callback: types.CallbackQuery):
            await callback.message.answer("🏦 Please send your new *Safe Wallet Address*:", parse_mode="Markdown")
            await callback.answer()

        @self.dp.callback_query(F.data == "ignore")
        async def handle_ignore(callback: types.CallbackQuery):
            await callback.message.edit_text("✅ Alert Dismissed.")
            await callback.answer()

        @self.dp.callback_query(F.data == "status_refresh")
        async def handle_status_refresh(callback: types.CallbackQuery):
            await self.status_command(callback.message)
            await callback.answer()

        @self.dp.callback_query(F.data == "settings_menu")
        async def handle_settings_menu(callback: types.CallbackQuery):
            await self.show_settings_menu()
            await callback.answer()

        @self.dp.callback_query(F.data == "panic_confirm")
        async def handle_panic_confirm(callback: types.CallbackQuery):
            await self.panic_command(callback.message)
            await callback.answer()

        @self.dp.callback_query(F.data == "toggle_skimming")
        async def handle_toggle_skimming(callback: types.CallbackQuery):
            user_id = str(callback.from_user.id)
            state = await self.db.get_user_state(user_id)
            current = state['skimming_enabled'] if state else False
            await self.db.update_user_state(user_id, skimming_enabled=not current)
            new_status = "ON" if not current else "OFF"
            await callback.message.edit_text(f"🍯 Auto-Skimming is now: *{new_status}*", parse_mode="Markdown")
            await callback.answer(f"Skimming {new_status}")

        # Bind Command Handlers
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.panic_command, Command("panic"))
        self.dp.message.register(self.vault_command, Command("vault"))
        self.dp.message.register(self.status_command, Command("status"))
        self.dp.message.register(self.remove_wallet_command, Command("remove_wallet"))
        self.dp.message.register(self.set_safe_command, Command("set_safe"))
        self.dp.message.register(self.add_monitored_command, Command("add_monitored"))
        self.dp.message.register(self.whitelist_command, Command("whitelist"))
        self.dp.message.register(self.blacklist_command, Command("blacklist"))
        self.dp.message.register(self.history_command, Command("history"))
        self.dp.message.register(self.gas_command, Command("gas"))
        self.dp.message.register(self.health_command, Command("health"))
        self.dp.message.register(self.skim_command, Command("skim"))
        self.dp.message.register(self.settings_command, Command("settings"))
        self.dp.message.register(self.report_command, Command("report"))
        self.dp.message.register(self.test_attack_command, Command("test_attack"))

    async def start_command(self, message: types.Message):
        welcome_text = (
            "🛡️ *GUARDIAN NEXUS ULTRA-FRONTIER*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "I am your automated security sentinel. I protect your Solana assets with sub-millisecond rescue logic.\n\n"
            "📂 *SETUP COMMANDS*\n"
            "• /add_monitored - Watch a new wallet\n"
            "• /set_safe - Set rescue destination\n"
            "• /vault - Securely store private keys\n\n"
            "🤖 *DEFENSE & HARVESTING*\n"
            "• /settings - Toggle Auto-Defense\n"
            "• /skim - Configure Bait Harvesting\n\n"
            "🚨 *EMERGENCY*\n"
            "• /panic - Global Rescue Sweep\n\n"
            "📊 *INSIGHTS*\n"
            "• /status - Live Balances & Setup\n"
            "• /history - Recent Threat Logs\n"
            "• /health - System & RPC Check\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *Tip:* Click the 'Menu' button to see all commands instantly."
        )
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📊 Show Status", callback_data="status_refresh"))
        builder.row(types.InlineKeyboardButton(text="⚙️ Open Settings", callback_data="settings_menu"))
        builder.row(types.InlineKeyboardButton(text="🚨 GLOBAL PANIC 🚨", callback_data="panic_confirm"))
        await message.answer(welcome_text, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def panic_command(self, message: types.Message):
        user_id = str(message.from_user.id)
        await message.answer("⚠️ *GLOBAL PANIC INITIATED* ⚠️\nConnecting to Secure Vault...")
        if self.emergency_service:
            success = await self.emergency_service.execute_all(user_id, self.db)
            if success:
                await message.answer("✅ *CRITICAL:* All assets successfully swept to Safe Wallet.")
            else:
                await message.answer("❌ *PANIC FAILED:* No encrypted keys found in vault or balance too low.")
        else:
            await message.answer("❌ *SYSTEM ERROR:* Emergency Service offline.")

    async def vault_command(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ Usage: `/vault [Address] [Private_Key]`", parse_mode="Markdown")
            return
        address, privkey = parts[1], parts[2]
        user_id = str(message.from_user.id)
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Could not delete vault message: {e}")
        from utils.encryption_utils import EncryptionManager
        encryptor = EncryptionManager(config.ENCRYPTION_KEY)
        encrypted = encryptor.encrypt(privkey)
        await self.db.store_vault_key(address, encrypted)
        await message.answer(f"🔒 *SECURE VAULT:* Key for `{address[:8]}...` encrypted and saved. (Original message deleted)", parse_mode="Markdown")

    async def status_command(self, message: types.Message):
        user_id = str(message.from_user.id)
        state = await self.db.get_user_state(user_id)
        if not state:
            await message.answer("❌ No user profile found. Use /start.")
            return
        wallets = json.loads(state['monitored_wallets_json'] if state['monitored_wallets_json'] else '[]')
        safe_wallet = state['safe_wallet_address'] or "Not Configured"
        auto_def = "ON" if state['auto_defense'] else "OFF"
        status_text = (
            f"🛡️ *Guardian Status Update*\n\n"
            f"🏦 *Safe Wallet:* `{safe_wallet}`\n"
            f"🤖 *Auto-Defense:* `{auto_def}`\n"
            f"👀 *Monitored Wallets:* {len(wallets)}\n"
        )
        for addr in wallets:
            from utils.solana_client import SolanaClient
            sc = SolanaClient()
            bal = await sc.get_balance(addr)
            status_text += f"• `{addr[:8]}...`: `{bal} SOL`\n"
        await message.answer(status_text, parse_mode="Markdown")

    async def remove_wallet_command(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Usage: `/remove_wallet [Address]`")
            return
        address, user_id = parts[1], str(message.from_user.id)
        state = await self.db.get_user_state(user_id)
        wallets = json.loads(state['monitored_wallets_json'] if state['monitored_wallets_json'] else '[]')
        if address in wallets:
            wallets.remove(address)
            await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(wallets))
            await self.db.delete_vault_key(address)
            await message.answer(f"🗑️ Wallet `{address}` removed from monitoring and vault.")
        else:
            await message.answer("❌ Wallet not found in your monitored list.")

    async def set_safe_command(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Usage: `/set_safe [Solana_Address]`", parse_mode="Markdown")
            return
        address, user_id = parts[1], str(message.from_user.id)
        await self.db.update_user_state(user_id, safe_wallet_address=address, safe_wallet_configured=True)
        await message.answer(f"✅ *Safe Wallet Saved:* `{address}`", parse_mode="Markdown")

    async def add_monitored_command(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Usage: `/add_monitored [Solana_Address]`", parse_mode="Markdown")
            return
        address, user_id = parts[1], str(message.from_user.id)
        state = await self.db.get_user_state(user_id)
        wallets = json.loads(state['monitored_wallets_json'] if state and state['monitored_wallets_json'] else '[]')
        if address not in wallets:
            wallets.append(address)
            await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(wallets))
            await message.answer(f"👀 *Monitoring Wallet:* `{address}`", parse_mode="Markdown")
        else:
            await message.answer("⚠️ Wallet is already being monitored.")

    async def whitelist_command(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Usage: `/whitelist [Address]`")
            return
        await self.db.add_to_whitelist(parts[1])
        await message.answer(f"✅ Address `{parts[1]}` added to Whitelist.")

    async def blacklist_command(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Usage: `/blacklist [Address]`")
            return
        await self.db.add_to_blacklist(parts[1], "Manual Blacklist")
        await message.answer(f"🚫 Address `{parts[1]}` manually blacklisted.")

    async def history_command(self, message: types.Message):
        logs = await self.db.get_history(5)
        if not logs:
            await message.answer("📁 No threat logs found.")
            return
        report = "📜 *Recent Threat History*\n\n"
        for log in logs:
            report += f"🕒 {log['timestamp']}\n⚖️ Score: `{log['risk_score']}`\n📍 Wallet: `{log['wallet_address'][:8]}...`\n\n"
        await message.answer(report, parse_mode="Markdown")

    async def gas_command(self, message: types.Message):
        from utils.solana_client import SolanaClient
        sc, tank = SolanaClient(), config.SAFE_WALLET_ADDRESS
        bal = await sc.get_balance(tank)
        await message.answer(f"⛽ *Gas Tank Balance:* `{bal} SOL`", parse_mode="Markdown")

    async def health_command(self, message: types.Message):
        from utils.solana_client import SolanaClient
        sc = SolanaClient()
        try:
            await sc.get_balance("GkYoTMJKKqzbaebzVkDS4KvNvbgFt5suFpAqx6LbMcSR")
            await message.answer("🟢 *SYSTEM HEALTH:* Normal\n📡 RPC: Connected (ATN)\n🛡️ Mesh: Synchronized", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"🔴 *SYSTEM HEALTH:* Critical\n📡 RPC Error: {str(e)[:50]}...", parse_mode="Markdown")

    async def skim_command(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ Usage: `/skim [Retain_Amount] [Threshold]`\nExample: `/skim 0.01 0.02`", parse_mode="Markdown")
            return
        try:
            retain, threshold, user_id = float(parts[1]), float(parts[2]), str(message.from_user.id)
            await self.db.update_user_state(user_id, skimming_retain=retain, skimming_threshold=threshold, skimming_enabled=True)
            await message.answer(f"🍯 *Auto-Skimming Configured!*\nRetain: `{retain} SOL`\nTrigger: `{threshold} SOL`", parse_mode="Markdown")
        except ValueError:
            await message.answer("❌ Invalid amounts. Please use numbers.")

    async def settings_command(self, message: types.Message):
        await self.show_settings_menu()

    async def report_command(self, message: types.Message):
        await message.answer("📢 Use the Dashboard or /report_center to see official links.")

    async def test_attack_command(self, message: types.Message):
        wallet = config.MONITORED_WALLETS[0] if config.MONITORED_WALLETS else "TestWallet123"
        await message.answer(f"🧪 *SIMULATING ATTACK* on `{wallet}`...", parse_mode="Markdown")
        await self.send_threat_alert(wallet_address=wallet, score=95, reasons=["Suspicious Program Interaction", "High Frequency Outflow"], tx_hash="Simulated_TX_Hash_123")

    async def send_threat_alert(self, wallet_address: str, score: int, reasons: list, tx_hash: str):
        message = (
            f"🚨 *THREAT DETECTED* 🚨\n\n"
            f"📍 *Wallet:* `{wallet_address}`\n"
            f"⚖️ *Risk Score:* `{score}/100`\n"
            f"🔍 *Reasons:* {', '.join(reasons)}\n"
            f"🔗 [View on Solscan](https://solscan.io/tx/{tx_hash})\n\n"
            f"What would you like to do?"
        )

        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🚨 EMERGENCY SWEEP 🚨", callback_data=f"sweep_{wallet_address}"))
        builder.row(types.InlineKeyboardButton(text="📢 REPORT INCIDENT", callback_data=f"report_{tx_hash}"))
        builder.row(types.InlineKeyboardButton(text="✅ Ignore", callback_data="ignore"))

        await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def show_settings_menu(self):
        message = "⚙️ *Guardian Settings*\nConfigure your bot's behavior:"
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🤖 Auto-Defense", callback_data="toggle_auto"))
        builder.row(types.InlineKeyboardButton(text="🍯 Auto-Skimming", callback_data="toggle_skimming"))
        builder.row(types.InlineKeyboardButton(text="🏦 Change Safe Wallet", callback_data="change_safe"))
        await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def send_status_update(self, message: str):
        await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown")

    async def start(self):
        logging.info("Telegram Bot: Starting polling...")
        
        # Register Menu Commands
        from aiogram.types import BotCommand
        await self.bot.set_my_commands([
            BotCommand(command="start", description="Open Security Dashboard"),
            BotCommand(command="status", description="Check Balances & Setup"),
            BotCommand(command="panic", description="🚨 GLOBAL EMERGENCY SWEEP"),
            BotCommand(command="settings", description="Configure Defense Modes"),
            BotCommand(command="vault", description="🔒 Securely Store Private Key"),
            BotCommand(command="add_monitored", description="Add Wallet to Watch-list"),
            BotCommand(command="set_safe", description="Set Rescue Destination"),
            BotCommand(command="skim", description="🍯 Configure Auto-Harvesting"),
            BotCommand(command="history", description="📜 View Threat History"),
            BotCommand(command="health", description="🟢 Check System Status")
        ])

        await self.dp.start_polling(self.bot)
