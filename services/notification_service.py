from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
import config
import logging

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

        @self.dp.callback_query(F.data == "ignore")
        async def handle_ignore(callback: types.CallbackQuery):
            await callback.message.edit_text("✅ Alert Dismissed.")
            await callback.answer()

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
            await message.answer("⚠️ *GLOBAL PANIC INITIATED* ⚠️\nConnecting to Secure Vault...")
            if self.emergency_service:
                success = await self.emergency_service.execute_all()
                if success:
                    await message.answer("✅ *CRITICAL:* All assets successfully swept to Safe Wallet.")
                else:
                    await message.answer("❌ *PANIC FAILED:* No encrypted keys found in vault. Please configure your wallets in the dashboard.")
            else:
                await message.answer("❌ *SYSTEM ERROR:* Emergency Service offline.")

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
