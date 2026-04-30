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
        async def handle_manual_sweep(callback: types.CallbackQuery):
            wallet = callback.data.split("_")[1]
            await callback.message.answer(f"🚀 Executing Emergency Sweep for {wallet}...")
            if self.emergency_service:
                await self.emergency_service.sweep_all(wallet, config.SAFE_WALLET_ADDRESS)
            await callback.answer("Sweep Initiated")

        @self.dp.callback_query(F.data == "toggle_auto")
        async def handle_toggle_auto(callback: types.CallbackQuery):
            user_id = str(callback.from_user.id)
            # Toggle in DB
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

        @self.dp.message(Command("test_attack"))
        async def test_attack_command(message: types.Message):
            wallet = config.MONITORED_WALLETS[0] if config.MONITORED_WALLETS else "TestWallet123"
            await message.answer(f"🧪 *SIMULATING ATTACK* on `{wallet}`...", parse_mode="Markdown")
            await self.send_threat_alert(
                wallet_address=wallet,
                score=95,
                reasons=["Suspicious Program Interaction", "High Frequency Outflow"],
                tx_hash="Simulated_TX_Hash_123"
            )

        @self.dp.message(Command("start"))
        async def start_command(message: types.Message):
            welcome_text = (
                "🛡️ *Guardian Nexus Online*\n\n"
                "I am your automated security sentinel. I am currently monitoring your wallets for sub-millisecond threats.\n\n"
                "📜 *Available Commands:*\n"
                "/panic - Trigger Emergency Sweep\n"
                "/settings - Configure Defense Modes\n"
                "/report - File a Cyber Report"
            )
            await message.answer(welcome_text, parse_mode="Markdown")

        @self.dp.message(Command("panic"))
        async def panic_command(message: types.Message):
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

        @self.dp.message(Command("vault"))
        async def vault_command(message: types.Message):
            parts = message.text.split()
            if len(parts) < 3:
                await message.answer("❌ Usage: `/vault [Address] [Private_Key]`", parse_mode="Markdown")
                return
            
            address, privkey = parts[1], parts[2]
            user_id = str(message.from_user.id)
            
            # Delete message immediately for security
            try:
                await message.delete()
            except Exception as e:
                logging.warning(f"Could not delete vault message: {e}")

            from utils.encryption_utils import EncryptionManager
            encryptor = EncryptionManager(config.ENCRYPTION_KEY)
            encrypted = encryptor.encrypt(privkey)
            
            await self.db.store_vault_key(address, encrypted)
            await message.answer(f"🔒 *SECURE VAULT:* Key for `{address[:8]}...` encrypted and saved. (Original message deleted)", parse_mode="Markdown")

        @self.dp.message(Command("status"))
        async def status_command(message: types.Message):
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
                # Get balance via SolanaClient
                from utils.solana_client import SolanaClient
                sc = SolanaClient()
                bal = await sc.get_balance(addr)
                status_text += f"• `{addr[:8]}...`: `{bal} SOL`\n"

            await message.answer(status_text, parse_mode="Markdown")

        @self.dp.message(Command("remove_wallet"))
        async def remove_wallet_command(message: types.Message):
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("❌ Usage: `/remove_wallet [Address]`")
                return
            
            address = parts[1]
            user_id = str(message.from_user.id)
            state = await self.db.get_user_state(user_id)
            wallets = json.loads(state['monitored_wallets_json'] if state['monitored_wallets_json'] else '[]')
            
            if address in wallets:
                wallets.remove(address)
                await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(wallets))
                await self.db.delete_vault_key(address)
                await message.answer(f"🗑️ Wallet `{address}` removed from monitoring and vault.")
            else:
                await message.answer("❌ Wallet not found in your monitored list.")

        @self.dp.message(Command("set_safe"))
        async def set_safe_command(message: types.Message):
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("❌ Usage: `/set_safe [Solana_Address]`", parse_mode="Markdown")
                return
            
            address = parts[1]
            user_id = str(message.from_user.id)
            await self.db.update_user_state(user_id, safe_wallet_address=address, safe_wallet_configured=True)
            await message.answer(f"✅ *Safe Wallet Saved:* `{address}`", parse_mode="Markdown")

        @self.dp.message(Command("add_monitored"))
        async def add_monitored_command(message: types.Message):
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("❌ Usage: `/add_monitored [Solana_Address]`", parse_mode="Markdown")
                return
            
            address = parts[1]
            user_id = str(message.from_user.id)
            state = await self.db.get_user_state(user_id)
            wallets = json.loads(state['monitored_wallets_json'] if state and state['monitored_wallets_json'] else '[]')
            
            if address not in wallets:
                wallets.append(address)
                await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(wallets))
                await message.answer(f"👀 *Monitoring Wallet:* `{address}`", parse_mode="Markdown")
            else:
                await message.answer("⚠️ Wallet is already being monitored.")

        @self.dp.message(Command("settings"))
        async def settings_command(message: types.Message):
            await self.show_settings_menu()

        @self.dp.message(Command("report"))
        async def report_command(message: types.Message):
            await message.answer("📢 Use the Dashboard or /report_center to see official links.")

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
        builder.row(types.InlineKeyboardButton(text="🤖 Auto-Defense: ON", callback_data="toggle_auto"))
        builder.row(types.InlineKeyboardButton(text="🏦 Change Safe Wallet", callback_data="change_safe"))
        await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def send_status_update(self, message: str):
        await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown")

    async def start(self):
        logging.info("Telegram Bot: Starting polling...")
        await self.dp.start_polling(self.bot)
