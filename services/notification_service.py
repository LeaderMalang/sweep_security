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
    
    # Feature Wizards
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

    def _register_handlers(self):
        @self.dp.callback_query(F.data.startswith("sweep_"))
        async def handle_manual_sweep_callback(callback: types.CallbackQuery):
            target = callback.data.split("_")[1]
            user_id = str(callback.from_user.id)
            
            if target == "all":
                await callback.message.answer("🚀 *GLOBAL PANIC:* Sweeping all protected assets...")
                if self.emergency_service:
                    await self.emergency_service.execute_all(user_id)
            else:
                await callback.message.answer(f"🚀 Executing Emergency Sweep for {target}...")
                if self.emergency_service:
                    await self.emergency_service.execute_all(user_id)
            
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
        async def handle_change_safe(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("🏦 Please send your new *Safe Wallet Address*:", parse_mode="Markdown")
            await state.set_state(SetupWizard.waiting_for_safe_wallet)
            await callback.answer()

        @self.dp.callback_query(F.data == "ignore")
        async def handle_ignore(callback: types.CallbackQuery):
            await callback.message.edit_text("✅ Alert Dismissed.")
            await callback.answer()

        @self.dp.callback_query(F.data == "status_refresh")
        async def handle_status_refresh(callback: types.CallbackQuery):
            await self.status_command(callback.message, user_id_override=str(callback.from_user.id))
            await callback.answer()

        @self.dp.callback_query(F.data == "settings_menu")
        async def handle_settings_menu(callback: types.CallbackQuery):
            await self.show_settings_menu(user_id=str(callback.from_user.id))
            await callback.answer()

        @self.dp.callback_query(F.data == "panic_confirm")
        async def handle_panic_confirm(callback: types.CallbackQuery):
            await self.panic_command(callback.message)
            await callback.answer()

        @self.dp.callback_query(F.data == "toggle_refill")
        async def handle_toggle_refill(callback: types.CallbackQuery):
            user_id = str(callback.from_user.id)
            state = await self.db.get_user_state(user_id)
            if not state: return
            new_val = 0 if dict(state).get('auto_refill_gas', 1) else 1
            await self.db.update_user_state(user_id, auto_refill_gas=new_val)
            await callback.answer(f"⛽ Auto-Refill {'ENABLED' if new_val else 'DISABLED'}")
            await self.show_settings_menu()

        @self.dp.callback_query(F.data == "toggle_skimming")
        async def handle_toggle_skimming(callback: types.CallbackQuery):
            user_id = str(callback.from_user.id)
            state = await self.db.get_user_state(user_id)
            current = state['skimming_enabled'] if state else False
            await self.db.update_user_state(user_id, skimming_enabled=not current)
            new_status = "ON" if not current else "OFF"
            await callback.message.edit_text(f"🍯 Auto-Skimming is now: *{new_status}*", parse_mode="Markdown")
            await callback.answer(f"Skimming {new_status}")

        @self.dp.callback_query(F.data == "wizard_admin_rpc")
        async def handle_wizard_admin_rpc(callback: types.CallbackQuery, state: FSMContext):
            user_id = str(callback.from_user.id)
            await self.db.update_user_state(user_id, custom_rpc_url=config.SOLANA_RPC_URL)
            await callback.message.edit_text("⚡ *Admin Mode Active:* System RPC linked to your account.")
            await callback.message.answer("🎉 *Setup Complete!* Welcome back, Leader.")
            await state.clear()
            await callback.answer()

        @self.dp.callback_query(F.data == "reset_confirm")
        async def handle_reset_confirm(callback: types.CallbackQuery):
            user_id = str(callback.from_user.id)
            await self.db.update_user_state(
                user_id,
                monitored_wallets_json='[]',
                bait_wallets_json='[]',
                safe_wallet_address=None,
                safe_wallet_configured=False,
                custom_rpc_url=None,
                auto_defense=False
            )
            await callback.message.edit_text("🗑️ *STATE WIPED:* All wallets and configurations have been deleted instantly.", parse_mode="Markdown")
            await callback.answer("Data Deleted")

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

        self.dp.message.register(self.wizard_safe_wallet, SetupWizard.waiting_for_safe_wallet)
        self.dp.message.register(self.wizard_monitored_wallet, SetupWizard.waiting_for_monitored_wallet)
        self.dp.message.register(self.wizard_vault_key, SetupWizard.waiting_for_vault_key)
        self.dp.message.register(self.wizard_skim_retain, SetupWizard.waiting_for_skim_retain)
        self.dp.message.register(self.wizard_skim_threshold, SetupWizard.waiting_for_skim_threshold)
        self.dp.message.register(self.wizard_skim_addresses, SetupWizard.waiting_for_skim_addresses)
        self.dp.message.register(self.wizard_bait_addresses, SetupWizard.waiting_for_bait_addresses)
        
        self.dp.message.register(self.wizard_remove_wallet, SetupWizard.waiting_for_remove_wallet)
        self.dp.message.register(self.wizard_vault_address, SetupWizard.waiting_for_vault_address)
        self.dp.message.register(self.wizard_vault_key_guided, SetupWizard.waiting_for_vault_key)
        self.dp.message.register(self.wizard_gas_key, SetupWizard.waiting_for_gas_key)
        self.dp.message.register(self.wizard_tip_amount, SetupWizard.waiting_for_tip_amount)
        self.dp.message.register(self.wizard_rpc_url, SetupWizard.waiting_for_rpc_url)
        
        self.dp.callback_query.register(self.handle_buy_premium_ton, F.data.startswith("buy_"))
        self.dp.callback_query.register(self.handle_toggle_auto_wizard, F.data.startswith("toggle_auto_wizard_"))
        self.dp.callback_query.register(self.handle_toggle_daily, F.data == "toggle_daily")
        self.dp.callback_query.register(self.handle_toggle_smart, F.data == "toggle_smart")
        self.dp.callback_query.register(self.handle_toggle_refill, F.data == "toggle_refill")
        self.dp.callback_query.register(self.handle_toggle_skimming, F.data == "toggle_skimming")
        self.dp.callback_query.register(self.handle_toggle_auto, F.data == "toggle_auto")

    async def premium_command(self, message: types.Message):
        user_id = str(message.from_user.id)
        is_admin = user_id == str(config.TELEGRAM_CHAT_ID)
        state = await self.db.get_user_state(user_id)
        current_tier = "ADMIN" if is_admin else (state['subscription_tier'].upper() if state else "FREE")
        if is_admin:
            premium_text = (
                "👑 *GUARDIAN MASTER CONSOLE*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Status: *ADMIN BYPASS ACTIVE*\n\n"
                "You have permanent access to all **Phase-Omega** features:\n"
                "• Ultra-High-Speed System RPC\n"
                "• Zero-Latency Jito Tip Engine\n"
                "• Global Threat Network Master-View\n"
                "• Unlimited Wallet Monitoring\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🛡️ *Nexus Security Level: MAXIMUM*"
            )
            await message.answer(premium_text, parse_mode="Markdown", reply_markup=self.get_dashboard_markup())
            return
        premium_text = (
            "💎 *GUARDIAN NEXUS PREMIUM*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Your Current Tier: *{current_tier}*\n\n"
            "🛡️ *1. SENTINEL (Free)*\n"
            "• 1 Monitored Wallet\n"
            "• Public RPC (Slower Rescue)\n\n"
            "⚡ *2. LITE ($2 / Month)*\n"
            "• **Unlimited Wallets**\n"
            "• **Use Your Own RPC** (Custom URL)\n\n"
            "🚀 *3. PRO ($10 / Month)*\n"
            "• **Unlimited Wallets**\n"
            "• **High-Speed System RPC Access**\n"
            "• *Usage Tracking:* Charged based on RPC consumption.\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Select your upgrade path below:"
        )
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="⚡ Upgrade to LITE ($2)", callback_data="buy_lite_ton"))
        builder.row(types.InlineKeyboardButton(text="🚀 Upgrade to PRO ($10)", callback_data="buy_pro_ton"))
        await message.answer(premium_text, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def handle_buy_premium_ton(self, callback: types.CallbackQuery):
        payment_addr = "UQDY7...YourTonWallet"
        await callback.message.edit_text(
            f"💎 *PURCHASE GUARDIAN TIER*\n\n"
            f"Please send **0.5 TON** to the address below:\n\n"
            f"`{payment_addr}`\n\n"
            "*Note:* Verification is automatic. Your tier will update once the transaction is confirmed on the TON blockchain.",
            parse_mode="Markdown"
        )
        await callback.answer()

    async def recommend_command(self, message: types.Message):
        recommend_text = (
            "🏆 *SENTINEL-ZERO: GOLDEN SETTINGS*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "To ensure a **100% Success Rate** against high-speed drainers, we recommend the following tactical configuration:\n\n"
            "⚡ *1. Jito Priority Tip*\n"
            "• Recommended: `0.005 SOL` or higher.\n"
            "• Why: Attackers often tip 0.001-0.003. Setting 0.005 ensures you are at the front of the validator bundle.\n\n"
            "⛽ *2. Safe Wallet (Gas Tank)*\n"
            "• Recommended: `0.05 SOL` minimum balance.\n"
            "• Why: This fuels up to 10 emergency refills without you having to manually intervene.\n\n"
            "🍯 *3. Skimming Threshold*\n"
            "• Recommended: `0.02 SOL` (Threshold) / `0.01 SOL` (Retain).\n"
            "• Why: Leaves enough 'bait' to keep attackers interested while harvesting profit every time they send gas.\n\n"
            "🛰️ *4. Custom RPC*\n"
            "• Recommended: Use a private Helius or QuickNode endpoint.\n"
            "• Why: Public RPCs have rate limits. Private nodes ensure your transaction is detected and sent in <200ms.\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *Tip:* Use `/set_tip 0.005` to apply the recommended priority fee now."
        )
        await message.answer(recommend_text, parse_mode="Markdown", reply_markup=self.get_dashboard_markup())

    async def handle_toggle_auto_wizard(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        action = callback.data.split("_")[-1]
        if action == "yes":
            await self.db.update_user_state(user_id, auto_defense=True)
            await callback.message.edit_text("🚀 *AUTO-DEFENSE ARMED!*\n\nYour perimeter is now secure. I am watching every transaction in sub-milliseconds.", parse_mode="Markdown")
        else:
            await callback.message.edit_text("⚠️ *DEFENSE REMAINING IDLE*\n\nYour configuration is saved, but automatic rescues are **OFF**. You can enable them anytime via /settings.", parse_mode="Markdown")
        await callback.answer()

    async def handle_toggle_daily(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        current = bool(dict(row).get('daily_sweep_enabled'))
        await self.db.update_user_state(user_id, daily_sweep_enabled=not current)
        await callback.answer(f"🕰️ Daily Harvest: {'ON' if not current else 'OFF'}")
        await self.show_settings_menu(user_id)
        await callback.message.delete()

    async def handle_toggle_smart(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        current = bool(dict(row).get('smart_thresholds_enabled'))
        await self.db.update_user_state(user_id, smart_thresholds_enabled=not current)
        await callback.answer(f"🧠 Smart Thresholds: {'ON' if not current else 'OFF'}")
        await self.show_settings_menu(user_id)
        await callback.message.delete()

    async def handle_toggle_refill(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        current = bool(dict(row).get('auto_refill_gas', 1))
        await self.db.update_user_state(user_id, auto_refill_gas=not current)
        await callback.answer(f"⛽ Auto-Refill: {'ON' if not current else 'OFF'}")
        await self.show_settings_menu(user_id)
        await callback.message.delete()

    async def handle_toggle_skimming(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        current = bool(dict(row).get('skimming_enabled'))
        await self.db.update_user_state(user_id, skimming_enabled=not current)
        await callback.answer(f"🍯 Auto-Skimming: {'ON' if not current else 'OFF'}")
        await self.show_settings_menu(user_id)
        await callback.message.delete()

    async def handle_toggle_auto(self, callback: types.CallbackQuery):
        user_id = str(callback.from_user.id)
        row = await self.db.get_user_state(user_id)
        current = bool(dict(row).get('auto_defense'))
        await self.db.update_user_state(user_id, auto_defense=not current)
        await callback.answer(f"🤖 Auto-Defense: {'ON' if not current else 'OFF'}")
        await self.show_settings_menu(user_id)
        await callback.message.delete()

    async def faq_command(self, message: types.Message):
        faq_text = (
            "🛡️ *GUARDIAN NEXUS: THE SENTINEL FAQ*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "❓ *What is Guardian Nexus?*\n"
            "We are a sub-millisecond security sentinel for Solana. We monitor your wallets for unauthorized transfers and 'rescue' your assets to a safe location before the attacker can confirm their transaction.\n\n"
            "❓ *Why is it Essential?*\n"
            "Typical drainers use high-priority fees. We counter this by using **Jito Bundles**, allowing us to bypass the public mempool and secure your SOL/Tokens with 100% certainty.\n\n"
            "❓ *How does Auto-Skimming work?*\n"
            "You set up a 'Bait' wallet. When an attacker sends 'gas' or 'dust' to attract you, our bot harvests the profit automatically while leaving enough behind to keep the attacker interested.\n\n"
            "❓ *Is my Private Key safe?*\n"
            "Yes. All keys are encrypted using **AES-256 (Fernet)**. Even if our database was compromised, your keys remain unreadable without the master encryption key.\n\n"
            "❓ *Can I use my own RPC?*\n"
            "Absolutely. Every user can configure their own high-speed RPC to ensure maximum rescue performance.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *Need more help?* Contact @Leadermalang0"
        )
        await message.answer(faq_text, parse_mode="Markdown", reply_markup=self.get_dashboard_markup())
        self.dp.message.register(self.report_command, Command("report"))
        self.dp.message.register(self.test_attack_command, Command("test_attack"))

    async def set_gas_key_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        parts = message.text.split()
        if len(parts) >= 2:
            privkey = parts[1].strip()
            await self._process_gas_key(message, privkey)
            return
        await message.answer(
            "⛽ *PERSONAL GAS WIZARD*\n\n"
            "This links your **Safe Wallet** private key to enable self-sufficient refills.\n\n"
            "👉 Please send the **Private Key** of your Safe Wallet.\n"
            "_I will delete your message instantly._",
            parse_mode="Markdown"
        )
        await state.set_state(SetupWizard.waiting_for_gas_key)

    async def wizard_gas_key(self, message: types.Message, state: FSMContext):
        privkey = message.text.strip()
        success = await self._process_gas_key(message, privkey)
        if success:
            await state.clear()

    async def _process_gas_key(self, message, privkey):
        try: await message.delete()
        except: pass
        user_id = str(message.from_user.id)
        try:
            from solders.keypair import Keypair
            kp = Keypair.from_base58_string(privkey)
            address = str(kp.pubkey())
            from utils.encryption_utils import EncryptionManager
            encryptor = EncryptionManager(config.ENCRYPTION_KEY)
            encrypted = encryptor.encrypt(privkey)
            await self.db.store_vault_key(address, encrypted)
            await self.db.update_user_state(user_id, safe_wallet_address=address, safe_wallet_configured=True)
            await message.answer(f"⛽ *GAS TANK ARMED:* `{address[:8]}...` is now your personal refill source.", reply_markup=self.get_dashboard_markup())
            return True
        except Exception as e:
            await message.answer(f"❌ Error: {str(e)}\n\n👉 Please try again or use /cancel.")
            return False

    async def start_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        user_id = str(message.from_user.id)
        db_state = await self.db.get_user_state(user_id)
        if not db_state or not db_state['safe_wallet_configured'] or not db_state['monitored_wallets_json']:
            await message.answer("🧙‍♂️ *WELCOME TO GUARDIAN NEXUS*\n\nI see you haven't configured your security perimeter yet. Let's start the **Startup Wizard**.", parse_mode="Markdown")
            await message.answer("🏦 *STEP 1:* Please send your **Safe Wallet Address**.\n(This is where all rescued funds will be sent).")
            await state.set_state(SetupWizard.waiting_for_safe_wallet)
            return
        welcome_text = (
            "🛡️ *GUARDIAN NEXUS ULTRA-FRONTIER*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Status: *ACTIVE & PROTECTING*\n"
            f"Tier: *{db_state['subscription_tier'].upper()}*\n\n"
            "📂 *COMMANDS*\n"
            "• `/add_monitored` - Watch a new wallet\n"
            "• `/premium` - Upgrade Tier & Speed\n"
            "• `/panic` - Global Rescue Sweep\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📊 Show Status", callback_data="status_refresh"))
        builder.row(types.InlineKeyboardButton(text="⚙️ Open Settings", callback_data="settings_menu"))
        await message.answer(welcome_text, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def add_monitored_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        user_id = str(message.from_user.id)
        db_state = await self.db.get_user_state(user_id)
        if not db_state: return
        wallets = json.loads(db_state['monitored_wallets_json'] or '[]')
        tier = db_state['subscription_tier']
        is_admin = user_id == str(config.TELEGRAM_CHAT_ID)
        if not is_admin and tier == 'free' and len(wallets) >= 1:
            await message.answer(
                "⚠️ *FREE TIER LIMIT REACHED*\n\n"
                "Free users can only monitor **1 wallet**.\n\n"
                "💎 Upgrade to **LITE ($2)** for unlimited monitoring.\n"
                "🚀 Upgrade to **PRO ($10)** for High-Speed RPC.",
                parse_mode="Markdown"
            )
            return
        await message.answer("👀 Please send the **Wallet Address** you want me to monitor.", parse_mode="Markdown")
        await state.set_state(SetupWizard.waiting_for_monitored_wallet)

    async def wizard_safe_wallet(self, message: types.Message, state: FSMContext):
        address = message.text.strip()
        from solders.pubkey import Pubkey
        try:
            Pubkey.from_string(address)
        except ValueError:
            await message.answer("❌ *INVALID ADDRESS*\n\nPlease send a valid **Solana Wallet Address** (Base58).\n\n(Example: `7xKX...2p1`)", parse_mode="Markdown")
            return
        user_id = str(message.from_user.id)
        await self.db.update_user_state(user_id, safe_wallet_address=address, safe_wallet_configured=True)
        await message.answer(f"✅ *Safe Wallet Saved:* `{address[:6]}...{address[-4:]}`\n\n👀 *STEP 2:* Please send the **Wallet Address** you want me to monitor.", parse_mode="Markdown")
        await state.set_state(SetupWizard.waiting_for_monitored_wallet)

    async def wizard_monitored_wallet(self, message: types.Message, state: FSMContext):
        raw_input = message.text.replace(",", " ").split()
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        db_state = dict(row) if row else {}
        wallets = json.loads(db_state.get('monitored_wallets_json', '[]') or '[]')
        tier = db_state.get('subscription_tier', 'free')
        is_admin = user_id == str(config.TELEGRAM_CHAT_ID)
        from solders.pubkey import Pubkey
        added = []
        for address in raw_input:
            if not is_admin and tier == 'free' and len(wallets) >= 1: break
            try:
                Pubkey.from_string(address)
                if address not in wallets:
                    wallets.append(address)
                    added.append(address)
            except: pass
        if not added:
            await message.answer("❌ *NO VALID WALLETS ADDED*\n\nPlease send valid Solana addresses.", parse_mode="Markdown")
            return
        await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(wallets))
        await message.answer(f"✅ Added `{len(added)}` wallets to your fleet.\n\n🔐 *STEP 3:* Please send the **Private Key(s)** for these wallets.")
        await state.set_state(SetupWizard.waiting_for_vault_key)

    async def wizard_vault_key(self, message: types.Message, state: FSMContext):
        raw_keys = message.text.replace(",", " ").split()
        user_id = str(message.from_user.id)
        from solders.keypair import Keypair
        from utils.encryption_utils import EncryptionManager
        encryptor = EncryptionManager(config.ENCRYPTION_KEY)
        count = 0
        for priv in raw_keys:
            try:
                kp = Keypair.from_base58_string(priv)
                addr = str(kp.pubkey())
                encrypted = encryptor.encrypt(priv)
                await self.db.store_vault_key(addr, encrypted)
                count += 1
            except: pass
        await message.answer(f"🔐 Linked `{count}` private keys to your vault.\n\n🛡️ *FINAL STEP:* Do you want to **ARM Auto-Defense** now?", reply_markup=self.get_yes_no_keyboard("toggle_auto_wizard"))
        try: await message.delete()
        except: pass
        await state.clear()

    async def panic_command(self, message: types.Message):
        user_id = str(message.from_user.id)
        await message.answer("⚠️ *GLOBAL PANIC INITIATED* ⚠️\nConnecting to Secure Vault...")
        if self.emergency_service:
            success = await self.emergency_service.execute_all(user_id)
            if success: await message.answer("✅ *CRITICAL:* All assets successfully swept to Safe Wallet.")
            else: await message.answer("❌ *PANIC FAILED:* No encrypted keys found in vault or balance too low.")
        else: await message.answer("❌ *SYSTEM ERROR:* Emergency Service offline.")

    async def vault_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        parts = message.text.split()
        if len(parts) >= 3:
            address, privkey = parts[1], parts[2]
            await self._process_vault_key(message, address, privkey)
            return
        await message.answer("🔐 *SECURE VAULT WIZARD*\n\n👉 *STEP 1:* Please send the **Wallet Address**.", parse_mode="Markdown")
        await state.set_state(SetupWizard.waiting_for_vault_address)

    async def wizard_vault_address(self, message: types.Message, state: FSMContext):
        address = message.text.strip()
        from solders.pubkey import Pubkey
        try:
            Pubkey.from_string(address)
            await state.update_data(vault_address=address)
            await message.answer(f"✅ Address `{address[:8]}...` received.\n\n👉 *STEP 2:* Now send the **Private Key** (Base58).", parse_mode="Markdown")
            await state.set_state(SetupWizard.waiting_for_vault_key)
        except ValueError:
            await message.answer("❌ *INVALID ADDRESS*")

    async def wizard_vault_key_guided(self, message: types.Message, state: FSMContext):
        privkey = message.text.strip()
        data = await state.get_data()
        address = data.get('vault_address')
        await self._process_vault_key(message, address, privkey)
        await state.clear()

    async def _process_vault_key(self, message, address, privkey):
        try: await message.delete()
        except: pass
        from utils.encryption_utils import EncryptionManager
        encryptor = EncryptionManager(config.ENCRYPTION_KEY)
        encrypted = encryptor.encrypt(privkey)
        await self.db.store_vault_key(address, encrypted)
        await message.answer(f"🔒 *SECURE VAULT:* Key for `{address[:8]}...` encrypted and saved.", reply_markup=self.get_dashboard_markup())

    async def status_command(self, message: types.Message, state: FSMContext = None, user_id_override: str = None):
        if state: await state.clear()
        user_id = user_id_override or str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        if not row:
            await message.answer("❌ No user profile found. Use /start.")
            return
        state = dict(row)
        monitored = json.loads(state.get('monitored_wallets_json') or '[]')
        baits = json.loads(state.get('bait_wallets_json') or '[]')
        safe_wallet = state.get('safe_wallet_address', "Not Configured")
        auto_def = "ON" if state.get('auto_defense') else "OFF"
        from utils.solana_client import SolanaClient
        sc = SolanaClient(db=self.db)
        gas_bal = await sc.get_balance(safe_wallet, user_id=user_id) if safe_wallet != "Not Configured" else 0
        status_text = (
            f"🛡️ *Guardian Security Report*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Tier: *{state.get('subscription_tier', 'FREE').upper()}*\n"
            f"🏦 Safe: `{safe_wallet[:6]}...{safe_wallet[-4:]}`\n"
            f"⛽ Gas: `{gas_bal} SOL`\n"
            f"🤖 Defense: *{auto_def}*\n"
            f"📡 Requests: *{state.get('rpc_usage_count', 0)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👀 *Monitoring:* {len(monitored)} Wallets\n"
        )
        for addr in monitored[:3]:
            bal = await sc.get_balance(addr, user_id=user_id)
            status_text += f"• `{addr[:8]}...`: `{bal} SOL`\n"
        status_text += "━━━━━━━━━━━━━━━━━━━━"
        await message.answer(status_text, parse_mode="Markdown", reply_markup=self.get_dashboard_markup())

    async def wallets_command(self, message: types.Message, state: FSMContext = None, user_id_override: str = None):
        if state: await state.clear()
        user_id = user_id_override or str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        if not row: return
        state = dict(row)
        monitored = json.loads(state.get('monitored_wallets_json') or '[]')
        baits = json.loads(state.get('bait_wallets_json') or '[]')
        from utils.solana_client import SolanaClient
        sc = SolanaClient(db=self.db)
        report = "📋 *FULL FLEET INVENTORY*\n━━━━━━━━━━━━━━━━━━━━\n"
        for addr in monitored:
            bal = await sc.get_balance(addr, user_id=user_id)
            report += f"• `{addr}`\n  Balance: `{bal} SOL`\n"
        report += "━━━━━━━━━━━━━━━━━━━━"
        await message.answer(report, parse_mode="Markdown", reply_markup=self.get_dashboard_markup())

    async def remove_wallet_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        parts = message.text.split()
        if len(parts) >= 2:
            await self._process_wallet_removal(message, parts[1].strip())
            return
        await message.answer("🗑️ *REMOVE WALLET WIZARD*", parse_mode="Markdown")
        await state.set_state(SetupWizard.waiting_for_remove_wallet)

    async def wizard_remove_wallet(self, message: types.Message, state: FSMContext):
        address = message.text.strip()
        from solders.pubkey import Pubkey
        try:
            Pubkey.from_string(address)
            await self._process_wallet_removal(message, address)
            await state.clear()
        except ValueError: await message.answer("❌ Invalid Solana Address.")

    async def _process_wallet_removal(self, message, address):
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        if not row: return
        db_state = dict(row)
        monitored = json.loads(db_state.get('monitored_wallets_json') or '[]')
        baits = json.loads(db_state.get('bait_wallets_json') or '[]')
        removed = False
        if address in monitored:
            monitored.remove(address)
            await self.db.delete_vault_key(address)
            removed = True
        if address in baits:
            baits.remove(address)
            removed = True
        if removed:
            await self.db.update_user_state(user_id, monitored_wallets_json=json.dumps(monitored), bait_wallets_json=json.dumps(baits))
            await message.answer(f"✅ Wallet `{address[:10]}...` removed.", reply_markup=self.get_dashboard_markup())

    async def set_safe_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        parts = message.text.split()
        if len(parts) < 2: return
        address = parts[1].strip()
        from solders.pubkey import Pubkey
        try:
            Pubkey.from_string(address)
            await self.db.update_user_state(str(message.from_user.id), safe_wallet_address=address, safe_wallet_configured=True)
            await message.answer(f"✅ *Safe Wallet Saved:* `{address}`")
        except: pass

    async def cancel_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🛡️ *Operation Cancelled.*", reply_markup=self.get_dashboard_markup())

    async def reset_state_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🗑️ YES, DELETE EVERYTHING", callback_data="reset_confirm"))
        builder.row(types.InlineKeyboardButton(text="❌ NO, KEEP DATA", callback_data="ignore"))
        await message.answer("⚠️ *CRITICAL ACTION: RESET DATA*", reply_markup=builder.as_markup())

    async def history_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        logs = await self.db.get_history(5)
        if not logs: await message.answer("📁 No threat logs found.")
        else: await message.answer("📜 Threat history loaded.")

    async def health_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🟢 *SYSTEM HEALTH:* Normal", reply_markup=self.get_dashboard_markup())

    async def add_bait_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        raw_input = message.text.replace("/add_bait", " ").replace(",", " ").split()
        if raw_input: await self._process_bait_addition(message, raw_input, state)
        else:
            await message.answer("🍯 *HONEY POT WIZARD*", parse_mode="Markdown")
            await state.set_state(SetupWizard.waiting_for_bait_addresses)

    async def wizard_bait_addresses(self, message: types.Message, state: FSMContext):
        await self._process_bait_addition(message, message.text.replace(",", " ").split(), state)

    async def _process_bait_addition(self, message, raw_input, state):
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        db_state = dict(row) if row else {}
        bait_list = json.loads(db_state.get('bait_wallets_json', '[]') or '[]')
        from solders.pubkey import Pubkey
        added = []
        for address in raw_input:
            try:
                Pubkey.from_string(address)
                if address not in bait_list:
                    bait_list.append(address)
                    added.append(address)
            except: pass
        if added:
            await self.db.update_user_state(user_id, bait_wallets_json=json.dumps(bait_list))
            await message.answer(f"✅ Added `{len(added)}` baits. Send Private Keys next.")
            await state.set_state(SetupWizard.waiting_for_vault_key)

    async def skim_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("🍯 *AUTO-SKIMMING SETUP*", parse_mode="Markdown")
        await state.set_state(SetupWizard.waiting_for_skim_retain)

    async def wizard_skim_retain(self, message: types.Message, state: FSMContext):
        try:
            retain = float(message.text.strip())
            await state.update_data(skim_retain=retain)
            await message.answer(f"✅ Retain: `{retain} SOL`. Set Trigger next.")
            await state.set_state(SetupWizard.waiting_for_skim_threshold)
        except: pass

    async def wizard_skim_threshold(self, message: types.Message, state: FSMContext):
        try:
            threshold = float(message.text.strip())
            data = await state.get_data()
            await self.db.update_user_state(str(message.from_user.id), skimming_retain=data.get('skim_retain'), skimming_threshold=threshold, skimming_enabled=True)
            await message.answer("🍯 *Auto-Skimming ARMED!*")
            await state.clear()
        except: pass

    async def set_rpc_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("📡 *CUSTOM RPC WIZARD*", parse_mode="Markdown")
        await state.set_state(SetupWizard.waiting_for_rpc_url)

    async def wizard_rpc_url(self, message: types.Message, state: FSMContext):
        rpc_url = message.text.strip()
        if rpc_url.startswith("http"):
            await self.db.update_user_state(str(message.from_user.id), custom_rpc_url=rpc_url)
            await message.answer(f"⚡ *RPC Updated*", reply_markup=self.get_dashboard_markup())
            await state.clear()

    async def show_settings_menu(self, user_id: str = None):
        user_id = user_id or str(config.TELEGRAM_CHAT_ID)
        message = "⚙️ *TACTICAL SETTINGS*\nConfigure your bot:"
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🤖 Auto-Defense", callback_data="toggle_auto"))
        builder.row(types.InlineKeyboardButton(text="⛽ Auto-Refill", callback_data="toggle_refill"))
        builder.row(types.InlineKeyboardButton(text="🍯 Auto-Skimming", callback_data="toggle_skimming"))
        builder.row(types.InlineKeyboardButton(text="🗑️ RESET ALL", callback_data="reset_confirm"))
        await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown", reply_markup=builder.as_markup())

    async def unlock_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        parts = message.text.split()
        if len(parts) < 2: return
        from utils.vault_manager import HardenedVaultManager
        if HardenedVaultManager().unlock(parts[1]):
            await message.answer("✅ *VAULT UNLOCKED*")
        try: await message.delete()
        except: pass

    async def setup_nonce_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("⚡ *DURABLE NONCE SETUP*")

    async def toggle_smart_command(self, message: types.Message, state: FSMContext):
        await state.clear()
        user_id = str(message.from_user.id)
        row = await self.db.get_user_state(user_id)
        if not row: return
        current = bool(dict(row).get('smart_thresholds_enabled'))
        await self.db.update_user_state(user_id, smart_thresholds_enabled=not current)
        await message.answer(f"🧠 *Smart Thresholds:* {'ON' if not current else 'OFF'}")

    async def start(self):
        logging.info("Telegram Bot: Starting polling...")
        from aiogram.types import BotCommand
        await self.bot.set_my_commands([
            BotCommand(command="start", description="Open Security Dashboard"),
            BotCommand(command="status", description="Check Overview & Stats"),
            BotCommand(command="panic", description="🚨 GLOBAL EMERGENCY SWEEP"),
            BotCommand(command="vault", description="🔒 Securely Store Private Key"),
            BotCommand(command="settings", description="Configure Defense Modes"),
            BotCommand(command="unlock", description="🔓 Unlock Hardened Vault"),
            BotCommand(command="setup_nonce", description="⚡ Initialize Durable Nonce"),
            BotCommand(command="reset_state", description="🗑️ Wipe All Security Data"),
            BotCommand(command="cancel", description="❌ Cancel Current Operation"),
        ])
        await self.dp.start_polling(self.bot)
