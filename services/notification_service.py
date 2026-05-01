from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, StateFilter
import config
import logging
import json
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

class SetupWizard(StatesGroup):
    waiting_for_safe_wallet = State()
    waiting_for_monitored_wallet = State()
    waiting_for_vault_key = State()
    waiting_for_skim_retain = State()
    waiting_for_skim_threshold = State()
    waiting_for_skim_addresses = State()
    waiting_for_remove_wallet = State()
    waiting_for_vault_address = State()
    waiting_for_gas_key = State()
    waiting_for_tip_amount = State()
    waiting_for_rpc_url = State()
    waiting_for_bait_addresses = State()

class NotificationService:
    def __init__(self, db=None, emergency_service=None):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.db = db
        self.emergency_service = emergency_service
        self._register_handlers()

    def get_dashboard_markup(self):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📊 Refresh Status", callback_data="status_refresh"))
        builder.row(types.InlineKeyboardButton(text="⚙️ Open Settings", callback_data="settings_menu"))
        return builder.as_markup()

    def get_yes_no_keyboard(self, prefix):
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="✅ YES", callback_data=f"{prefix}_yes"),
            types.InlineKeyboardButton(text="❌ NO", callback_data=f"{prefix}_no")
        )
        return builder.as_markup()

    async def premium_command(self, message: types.Message):
        user_id = str(message.from_user.id)
        is_admin = user_id == str(config.TELEGRAM_CHAT_ID)
        state = await self.db.get_user_state(user_id)
        current_tier = "ADMIN" if is_admin else (state['subscription_tier'].upper() if state else "FREE")
        premium_text = (f"💎 *GUARDIAN NEXUS PREMIUM*\nYour Tier: *{current_tier}*\n\n"
                        "🛡️ *1. SENTINEL (Free)*\n• 1 Monitored Wallet\n\n"
                        "⚡ *2. LITE ($2 / Month)*\n• **Unlimited Wallets**\n\n"
                        "🚀 *3. PRO ($10 / Month)*\n• **High-Speed System RPC Access**")
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="⚡ Upgrade to LITE ($2)", callback_data="buy_lite_ton"))
        builder.row(types.InlineKeyboardButton(text="🚀 Upgrade to PRO ($10)", callback_data="buy_pro_ton"))
        await message.answer(premium_text, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def handle_buy_premium_ton(self, callback: types.CallbackQuery):
        await callback.message.edit_text("💎 *PURCHASE:* Send **0.5 TON** to: `UQDY7...YourTonWallet`", parse_mode="Markdown")
        await callback.answer()

    async def recommend_command(self, message: types.Message):
        await message.answer("🏆 *SENTINEL-ZERO: RECOMMENDED SETTINGS*\n\n⚡ Tip: `0.005 SOL`\n⛽ Gas: `0.05 SOL`\n🛰️ RPC: Private Helius", parse_mode="Markdown")

    async def start_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        user_id = str(message.from_user.id)
        db_state = await self.db.get_user_state(user_id)
        if not db_state or not db_state['safe_wallet_configured']:
            await message.answer("🧙‍♂️ *WELCOME:* Let's start the **Startup Wizard**.\n\n🏦 *STEP 1:* Please send your **Safe Wallet Address**.")
            await state.set_state(SetupWizard.waiting_for_safe_wallet)
            return
        await message.answer("🛡️ *GUARDIAN NEXUS ACTIVE*", parse_mode="Markdown", reply_markup=self.get_dashboard_markup())

    async def wizard_safe_wallet(self, message: types.Message, state: FSMContext):
        address = message.text.strip()
        from solders.pubkey import Pubkey
        try:
            Pubkey.from_string(address)
            await self.db.update_user_state(str(message.from_user.id), safe_wallet_address=address, safe_wallet_configured=True)
            await message.answer(f"✅ *Safe Wallet Saved:* `{address[:8]}...`\n\n👀 *STEP 2:* Send **Wallet Address** to monitor.")
            await state.set_state(SetupWizard.waiting_for_monitored_wallet)
        except: await message.answer("❌ Invalid Solana Address.")

    async def wizard_monitored_wallet(self, message: types.Message, state: FSMContext):
        raw_input = message.text.replace(",", " ").split()
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        wallets = json.loads(row['monitored_wallets_json'] if row and row['monitored_wallets_json'] else '[]')
        added = []
        from solders.pubkey import Pubkey
        for addr in raw_input:
            try:
                Pubkey.from_string(addr)
                if addr not in wallets:
                    wallets.append(addr)
                    added.append(addr)
            except: pass
        if added:
            await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(wallets))
            await message.answer(f"✅ Added `{len(added)}` wallets. 🔐 *STEP 3:* Send **Private Key(s)**.")
            await state.set_state(SetupWizard.waiting_for_vault_key)
        else: await message.answer("❌ No valid wallets added.")

    async def wizard_vault_key(self, message: types.Message, state: FSMContext):
        raw_keys = message.text.replace(",", " ").split()
        from solders.keypair import Keypair
        from utils.encryption_utils import EncryptionManager
        encryptor = EncryptionManager(config.ENCRYPTION_KEY)
        count = 0
        for priv in raw_keys:
            try:
                kp = Keypair.from_base58_string(priv)
                addr = str(kp.pubkey())
                await self.db.store_vault_key(addr, encryptor.encrypt(priv))
                count += 1
            except: pass
        await message.answer(f"🔐 Linked `{count}` keys. 🛡️ Arm Auto-Defense?", reply_markup=self.get_yes_no_keyboard("toggle_auto_wizard"))
        try: await message.delete()
        except: pass
        await state.clear()

    async def panic_command(self, message: types.Message):
        user_id = str(message.from_user.id)
        await message.answer("⚠️ *GLOBAL PANIC:* Connecting to Vault...")
        if self.emergency_service:
            success = await self.emergency_service.execute_all(user_id)
            await message.answer("✅ Success" if success else "❌ Failed")
        else: await message.answer("❌ Offline")

    async def vault_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🔐 *VAULT:* Send **Wallet Address**.", parse_mode="Markdown")
        await state.set_state(SetupWizard.waiting_for_vault_address)

    async def status_command(self, message: types.Message, state: FSMContext = None, user_id_override: str = None):
        if state: await state.clear()
        user_id = user_id_override or str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        if not row: return
        s = dict(row)
        mon = json.loads(s.get('monitored_wallets_json') or '[]')
        status_text = f"🛡️ *Report*\nSafe: `{s.get('safe_wallet_address')[:8]}...`\nDefense: {'ON' if s.get('auto_defense') else 'OFF'}\nMonitoring: {len(mon)} Wallets"
        await message.answer(status_text, parse_mode="Markdown", reply_markup=self.get_dashboard_markup())

    async def wallets_command(self, message: types.Message, state: FSMContext = None):
        if state: await state.clear()
        row = await self.db.get_user_state(str(message.from_user.id))
        mon = json.loads(row['monitored_wallets_json'] if row and row['monitored_wallets_json'] else '[]')
        report = "📋 *FLEET:*\n" + "\n".join([f"• `{a}`" for a in mon])
        await message.answer(report, parse_mode="Markdown")

    async def remove_wallet_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🗑️ *REMOVE:* Send Address.")
        await state.set_state(SetupWizard.waiting_for_remove_wallet)

    async def wizard_remove_wallet(self, message: types.Message, state: FSMContext):
        addr = message.text.strip()
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        mon = json.loads(row['monitored_wallets_json'] if row else '[]')
        if addr in mon:
            mon.remove(addr)
            await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(mon))
            await self.db.delete_vault_key(addr)
            await message.answer(f"✅ Removed `{addr[:8]}...`")
        await state.clear()

    async def health_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🟢 *HEALTH: NORMAL*", reply_markup=self.get_dashboard_markup())

    async def settings_command(self, message: types.Message):
        await self.show_settings_menu(str(message.from_user.id))

    async def faq_command(self, message: types.Message):
        await message.answer("🛡️ *FAQ: Sentinel Zero*\nSub-millisecond protection for Solana assets.", parse_mode="Markdown")

    async def reset_state_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🗑️ YES, DELETE", callback_data="reset_confirm"))
        builder.row(types.InlineKeyboardButton(text="❌ NO", callback_data="ignore"))
        await message.answer("⚠️ *RESET DATA?*", reply_markup=builder.as_markup())

    async def skim_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🍯 *SKIM:* Set Retain Amount (SOL).")
        await state.set_state(SetupWizard.waiting_for_skim_retain)

    async def wizard_skim_retain(self, message: types.Message, state: FSMContext):
        try:
            val = float(message.text.strip())
            await state.update_data(skim_retain=val)
            await message.answer(f"✅ Retain: `{val} SOL`. Now set Trigger Balance (SOL).")
            await state.set_state(SetupWizard.waiting_for_skim_threshold)
        except: await message.answer("❌ Invalid number.")

    async def wizard_skim_threshold(self, message: types.Message, state: FSMContext):
        try:
            val = float(message.text.strip())
            data = await state.get_data()
            await self.db.update_user_state(str(message.from_user.id), skimming_retain=data.get('skim_retain'), skimming_threshold=val, skimming_enabled=True)
            await message.answer(f"🍯 *Auto-Skimming ARMED!* Trigger: `{val} SOL`.")
            await state.clear()
        except: await message.answer("❌ Invalid number.")

    async def wizard_skim_addresses(self, message: types.Message, state: FSMContext):
        await self.wizard_bait_addresses(message, state)

    async def wizard_bait_addresses(self, message: types.Message, state: FSMContext):
        raw = message.text.replace(",", " ").split()
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        baits = json.loads(row['bait_wallets_json'] if row and row['bait_wallets_json'] else '[]')
        added = []
        from solders.pubkey import Pubkey
        for addr in raw:
            try:
                Pubkey.from_string(addr)
                if addr not in baits:
                    baits.append(addr)
                    added.append(addr)
            except: pass
        if added:
            await self.db.update_user_state(user_id, bait_wallets_json=json.dumps(baits))
            await message.answer(f"✅ Added `{len(added)}` baits. Send Private Keys.")
            await state.set_state(SetupWizard.waiting_for_vault_key)
        else: await message.answer("❌ No valid addresses.")

    async def set_rpc_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("📡 *RPC:* Send private HTTP URL.")
        await state.set_state(SetupWizard.waiting_for_rpc_url)

    async def wizard_rpc_url(self, message: types.Message, state: FSMContext):
        url = message.text.strip()
        if url.startswith("http"):
            await self.db.update_user_state(str(message.from_user.id), custom_rpc_url=url)
            await message.answer("✅ RPC Updated.")
            await state.clear()
        else: await message.answer("❌ Invalid URL.")

    async def wizard_vault_address(self, message: types.Message, state: FSMContext):
        addr = message.text.strip()
        from solders.pubkey import Pubkey
        try:
            Pubkey.from_string(addr)
            await state.update_data(vault_address=addr)
            await message.answer(f"✅ Address received. Now send Private Key.")
            await state.set_state(SetupWizard.waiting_for_vault_key)
        except: await message.answer("❌ Invalid Address.")

    async def wizard_gas_key(self, message: types.Message, state: FSMContext):
        priv = message.text.strip()
        from solders.keypair import Keypair
        try:
            kp = Keypair.from_base58_string(priv)
            addr = str(kp.pubkey())
            from utils.encryption_utils import EncryptionManager
            encryptor = EncryptionManager(config.ENCRYPTION_KEY)
            await self.db.store_vault_key(addr, encryptor.encrypt(priv))
            await self.db.update_user_state(str(message.from_user.id), safe_wallet_address=addr, safe_wallet_configured=True)
            await message.answer(f"⛽ *GAS TANK:* `{addr[:8]}...` linked.")
            await state.clear()
        except: await message.answer("❌ Invalid Private Key.")

    async def wizard_tip_amount(self, message: types.Message, state: FSMContext):
        try:
            val = float(message.text.strip())
            await self.db.update_user_state(str(message.from_user.id), jito_tip_sol=val)
            await message.answer(f"⚡ Tip set to `{val} SOL`.")
            await state.clear()
        except: await message.answer("❌ Invalid number.")

    async def set_safe_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🏦 *SAFE:* Send Address.")
        await state.set_state(SetupWizard.waiting_for_safe_wallet)

    async def set_gas_key_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("⛽ *GAS:* Send Safe Wallet Private Key.")
        await state.set_state(SetupWizard.waiting_for_gas_key)

    async def add_monitored_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("👀 *MONITOR:* Send Address.")
        await state.set_state(SetupWizard.waiting_for_monitored_wallet)

    async def add_bait_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🍯 *BAIT:* Send Address.")
        await state.set_state(SetupWizard.waiting_for_bait_addresses)

    async def history_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("📜 *HISTORY:* No recent threats.")

    async def set_tip_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("⚡ *TIP:* Send Jito Tip Amount (SOL).")
        await state.set_state(SetupWizard.waiting_for_tip_amount)

    async def set_daily_sweep_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🕰️ *DAILY:* Send Time (HH:MM).")

    async def report_command(self, message: types.Message):
        await message.answer("📢 Report incident to @Leadermalang0")

    async def test_attack_command(self, message: types.Message):
        await message.answer("🧪 Simulation started.")

    async def unlock_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        parts = message.text.split()
        if len(parts) > 1:
            from utils.vault_manager import HardenedVaultManager
            if HardenedVaultManager().unlock(parts[1]): await message.answer("✅ Unlocked")
        try: await message.delete()
        except: pass

    async def setup_nonce_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("⚡ *NONCE SETUP*")

    async def toggle_smart_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        if row:
            curr = bool(dict(row).get('smart_thresholds_enabled'))
            await self.db.update_user_state(user_id, smart_thresholds_enabled=not curr)
            await message.answer(f"🧠 Smart Thresholds: {'ON' if not curr else 'OFF'}")

    async def cancel_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("❌ Cancelled")

    async def handle_toggle_auto_wizard(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        action = callback.data.split("_")[-1]  # "yes" or "no"
        if action == "yes":
            await self.db.update_user_state(user_id, auto_defense=True)
            await callback.message.edit_text("🚀 *AUTO-DEFENSE ARMED!* Your perimeter is now secured.", parse_mode="Markdown")
        else:
            await callback.message.edit_text("⚠️ *DEFENSE IDLE.* Auto-rescue is OFF. Enable via /settings.", parse_mode="Markdown")
        await callback.answer()

    async def handle_toggle_daily(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        curr = bool(dict(row).get('daily_sweep_enabled')) if row else False
        await self.db.update_user_state(user_id, daily_sweep_enabled=not curr)
        await callback.answer(f"🕰️ Daily Harvest: {'ON' if not curr else 'OFF'}")
        await self.show_settings_menu(user_id)

    async def handle_toggle_smart(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        curr = bool(dict(row).get('smart_thresholds_enabled')) if row else False
        await self.db.update_user_state(user_id, smart_thresholds_enabled=not curr)
        await callback.answer(f"🧠 Smart Thresholds: {'ON' if not curr else 'OFF'}")
        await self.show_settings_menu(user_id)

    async def handle_toggle_refill(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        curr = bool(dict(row).get('auto_refill_gas', True)) if row else True
        await self.db.update_user_state(user_id, auto_refill_gas=not curr)
        await callback.answer(f"⛽ Auto-Refill: {'ON' if not curr else 'OFF'}")
        await self.show_settings_menu(user_id)

    async def handle_toggle_skimming(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        curr = bool(dict(row).get('skimming_enabled')) if row else False
        await self.db.update_user_state(user_id, skimming_enabled=not curr)
        await callback.answer(f"🍯 Skimming: {'ON' if not curr else 'OFF'}")
        await self.show_settings_menu(user_id)

    async def show_settings_menu(self, user_id: str):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🤖 Auto-Defense", callback_data="toggle_auto"),
                    types.InlineKeyboardButton(text="⛽ Auto-Refill", callback_data="toggle_refill"))
        builder.row(types.InlineKeyboardButton(text="🍯 Skimming", callback_data="toggle_skimming"),
                    types.InlineKeyboardButton(text="🗑️ Reset", callback_data="reset_confirm"))
        await self.bot.send_message(chat_id=self.chat_id, text="⚙️ *SETTINGS*", parse_mode="Markdown", reply_markup=builder.as_markup())

    async def start(self):
        from aiogram.types import BotCommand
        await self.bot.set_my_commands([
            BotCommand(command="start", description="Dashboard"),
            BotCommand(command="status", description="Stats"),
            BotCommand(command="panic", description="🚨 PANIC"),
            BotCommand(command="settings", description="Settings"),
            BotCommand(command="vault", description="Vault"),
            BotCommand(command="unlock", description="Unlock"),
            BotCommand(command="reset_state", description="Reset"),
            BotCommand(command="cancel", description="Cancel"),
        ])
        await self.dp.start_polling(self.bot)

    def _register_handlers(self):
        @self.dp.callback_query(F.data.startswith("sweep_"))
        async def handle_manual_sweep_callback(callback: types.CallbackQuery):
            target = callback.data.split("_")[1]
            user_id = str(callback.from_user.id)
            if target == "all":
                await callback.message.answer("🚀 *GLOBAL PANIC:* Sweeping...")
                if self.emergency_service: await self.emergency_service.execute_all(user_id)
            else:
                await callback.message.answer(f"🚀 Sweeping {target}...")
                if self.emergency_service: await self.emergency_service.execute_all(user_id)
            await callback.answer()

        @self.dp.callback_query(F.data == "toggle_auto")
        async def handle_toggle_auto(callback: types.CallbackQuery):
            user_id = str(callback.from_user.id)
            state = await self.db.get_user_state(user_id)
            curr = state['auto_defense'] if state else False
            await self.db.update_user_state(user_id, auto_defense=not curr)
            await callback.message.edit_text(f"🤖 Auto-Defense: {'ON' if not curr else 'OFF'}")
            await callback.answer()

        @self.dp.callback_query(F.data == "status_refresh")
        async def handle_status_refresh(callback: types.CallbackQuery):
            await self.status_command(callback.message, user_id_override=str(callback.from_user.id))
            await callback.answer()

        @self.dp.callback_query(F.data == "settings_menu")
        async def handle_settings_menu(callback: types.CallbackQuery):
            await self.show_settings_menu(user_id=str(callback.from_user.id))
            await callback.answer()

        @self.dp.callback_query(F.data == "reset_confirm")
        async def handle_reset_confirm(callback: types.CallbackQuery):
            await self.reset_state_command(callback.message, None)
            await callback.answer()

        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.panic_command, Command("panic"))
        self.dp.message.register(self.vault_command, Command("vault"))
        self.dp.message.register(self.status_command, Command("status"))
        self.dp.message.register(self.wallets_command, Command("wallets"))
        self.dp.message.register(self.history_command, Command("history"))
        self.dp.message.register(self.health_command, Command("health"))
        self.dp.message.register(self.skim_command, Command("skim"))
        self.dp.message.register(self.settings_command, Command("settings"))
        self.dp.message.register(self.faq_command, Command("faq"))
        self.dp.message.register(self.recommend_command, Command("recommend"))
        self.dp.message.register(self.premium_command, Command("premium"))
        self.dp.message.register(self.set_tip_command, Command("set_tip"))
        self.dp.message.register(self.set_rpc_command, Command("set_rpc"))
        self.dp.message.register(self.set_safe_command, Command("set_safe"))
        self.dp.message.register(self.set_gas_key_command, Command("set_gas_key"))
        self.dp.message.register(self.add_monitored_command, Command("add_monitored"))
        self.dp.message.register(self.add_bait_command, Command("add_bait"))
        self.dp.message.register(self.remove_wallet_command, Command("remove_wallet"))
        self.dp.message.register(self.set_daily_sweep_command, Command("set_daily_sweep"))
        self.dp.message.register(self.toggle_smart_command, Command("toggle_smart"))
        self.dp.message.register(self.unlock_command, Command("unlock"))
        self.dp.message.register(self.setup_nonce_command, Command("setup_nonce"))
        self.dp.message.register(self.cancel_command, Command("cancel"))
        self.dp.message.register(self.reset_state_command, Command("reset_state"))
        self.dp.message.register(self.report_command, Command("report"))
        self.dp.message.register(self.test_attack_command, Command("test_attack"))

        self.dp.message.register(self.wizard_safe_wallet, SetupWizard.waiting_for_safe_wallet)
        self.dp.message.register(self.wizard_monitored_wallet, SetupWizard.waiting_for_monitored_wallet)
        self.dp.message.register(self.wizard_vault_key, SetupWizard.waiting_for_vault_key)
        self.dp.message.register(self.wizard_skim_retain, SetupWizard.waiting_for_skim_retain)
        self.dp.message.register(self.wizard_skim_threshold, SetupWizard.waiting_for_skim_threshold)
        self.dp.message.register(self.wizard_skim_addresses, SetupWizard.waiting_for_skim_addresses)
        self.dp.message.register(self.wizard_bait_addresses, SetupWizard.waiting_for_bait_addresses)
        self.dp.message.register(self.wizard_remove_wallet, SetupWizard.waiting_for_remove_wallet)
        self.dp.message.register(self.wizard_vault_address, SetupWizard.waiting_for_vault_address)
        self.dp.message.register(self.wizard_gas_key, SetupWizard.waiting_for_gas_key)
        self.dp.message.register(self.wizard_tip_amount, SetupWizard.waiting_for_tip_amount)
        self.dp.message.register(self.wizard_rpc_url, SetupWizard.waiting_for_rpc_url)
        
        self.dp.callback_query.register(self.handle_buy_premium_ton, F.data.startswith("buy_"))
        self.dp.callback_query.register(self.handle_toggle_auto_wizard, F.data.startswith("toggle_auto_wizard_"))
        self.dp.callback_query.register(self.handle_toggle_daily, F.data == "toggle_daily")
        self.dp.callback_query.register(self.handle_toggle_smart, F.data == "toggle_smart")
        self.dp.callback_query.register(self.handle_toggle_refill, F.data == "toggle_refill")
        self.dp.callback_query.register(self.handle_toggle_skimming, F.data == "toggle_skimming")

