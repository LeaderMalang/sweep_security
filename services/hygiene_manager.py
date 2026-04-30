import asyncio
import logging
from datetime import datetime, timedelta
import config

class HygieneManager:
    def __init__(self, db, notification_service):
        self.db = db
        self.notification_service = notification_service

    async def start_hygiene_loops(self):
        """Starts background tasks for daily and weekly hygiene checks."""
        logging.info("🧹 Hygiene Manager: Security loops active.")
        while True:
            await self._check_daily_hygiene()
            await self._check_weekly_audit()
            await asyncio.sleep(3600) # Check every hour

    async def _check_daily_hygiene(self):
        user_id = config.TELEGRAM_CHAT_ID
        state = await self.db.get_user_state(user_id)
        
        last_check = state['last_daily_check'] if state and state['last_daily_check'] else None
        
        should_prompt = False
        if not last_check:
            should_prompt = True
        else:
            last_dt = datetime.fromisoformat(last_check)
            if datetime.now() - last_dt > timedelta(hours=12):
                should_prompt = True

        if should_prompt:
            await self.notification_service.send_status_update(
                "🛡️ *DAILY HYGIENE CHECK*\n"
                "Please confirm your current security status:\n"
                "- Auto-lock is set to 5 min?\n"
                "- Transaction simulation is ON?\n"
                "- No new unknown connected apps?"
            )
            await self.db.update_user_state(user_id, last_daily_check=datetime.now().isoformat())

    async def _check_weekly_audit(self):
        user_id = config.TELEGRAM_CHAT_ID
        state = await self.db.get_user_state(user_id)
        
        last_audit = state[4] if state and state[4] else None
        
        should_prompt = False
        if not last_audit:
            should_prompt = True
        else:
            last_dt = datetime.fromisoformat(last_audit)
            if datetime.now() - last_dt > timedelta(days=7):
                should_prompt = True

        if should_prompt:
            checklist = (
                "📅 *WEEKLY SECURITY AUDIT*\n\n"
                "⏳ 1. Update Phantom extension\n"
                "⏳ 2. Check for fake Phantom versions\n"
                "⏳ 3. Revoke unused token approvals\n"
                "⏳ 4. Change spending password\n"
                "⏳ 5. Audit address book\n"
                "⏳ 6. Scan device for keyloggers\n\n"
                "Reply with /complete_audit once done."
            )
            await self.notification_service.send_status_update(checklist)
            await self.db.update_user_state(user_id, last_weekly_audit=datetime.now().isoformat())
