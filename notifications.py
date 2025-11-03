import asyncio
import logging
from datetime import datetime
from typing import Optional
from aiogram import Bot
from database import Database
from text_utils import escape_markdown
import text_utils

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db

    def _format_user_name(self, user: Optional[dict], fallback_id: int) -> str:
        if not user:
            return escape_markdown(f"ID: {fallback_id}")
        first_name = user.get('first_name')
        last_name = user.get('last_name')
        if first_name and last_name:
            return escape_markdown(f"{first_name} {last_name}")
        username = user.get('username')
        if username:
            return escape_markdown(username)
        return escape_markdown(f"ID: {fallback_id}")

    async def notify_curator_new_report(self, student_id: int, report_data: dict):
        """Уведомляет куратора о новом отчете от ученика"""
        curator = await self.db.get_student_curator(student_id)
        if not curator:
            return
        student_profile = await self.db.get_user_profile(student_id)
        student_name = self._format_user_name(student_profile, student_id)
        
        try:
            report_stage = escape_markdown(report_data['current_stage'])
            report_plans = escape_markdown(report_data['plans'])
            report_problems = escape_markdown(report_data['problems'])
            await self.bot.send_message(
                curator['user_id'],
                f"📝 *Новый отчет от {student_name}!*\n\n"
                f"🎯 *Этап:* {report_stage}\n"
                f"📋 *Планы:* {report_plans}\n"
                f"❓ *Проблемы:* {report_problems}\n\n"
                f"Используйте `/reports` для просмотра всех отчетов."
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить куратора {curator['user_id']}: {e}")

    async def notify_student_curator_assigned(self, student_id: int):
        """Уведомляет ученика о назначении куратора"""
        try:
            await self.bot.send_message(
                student_id,
                f"👨‍🏫 *К тебе назначен куратор!*\n\n"
                f"Теперь твои отчеты будут просматриваться куратором."
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить ученика {student_id}: {e}")

    async def notify_student_report_read(self, student_id: int, report_data: dict):
        """Уведомляет ученика о том, что куратор просмотрел его отчет"""
        try:
            report_stage = escape_markdown(report_data['current_stage'])
            report_plans = escape_markdown(report_data['plans'])
            report_problems = escape_markdown(report_data['problems'])
            await self.bot.send_message(
                student_id,
                "✅ *Твой отчет просмотрен куратором!*\n\n"
                f"🎯 *Этап:* {report_stage}\n"
                f"📋 *Планы:* {report_plans}\n"
                f"❓ *Проблемы:* {report_problems}"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить ученика {student_id}: {e}")

    async def send_weekly_reminders(self):
        recipients = await self._get_students_without_weekly_report()
        if not recipients:
            return
        message = text_utils.escape_markdown(
            "📝 *Время для еженедельного отчета!*\n\n"
            "Пожалуйста, заполни отчет по форме:\n"
            "• На каком сейчас этапе? (этап + тема)\n"
            "• Что планируешь делать?\n"
            "• Есть ли проблемы или вопросы?\n\n"
            "Используй кнопку '📝 Отправить отчет' для начала заполнения."
        )
        await self._deliver_reminders(recipients, message)

    async def send_daily_missing_report_reminders(self):
        recipients = await self._get_students_without_weekly_report()
        if not recipients:
            return
        message = text_utils.escape_markdown(
            "🔔 *Напоминание об отчете!*\n\n"
            "Мы ждем твой еженедельный отчет. Заполни форму, чтобы поделиться прогрессом."
        )
        await self._deliver_reminders(recipients, message)

    async def _deliver_reminders(self, recipients, message):
        tasks = [self._send_with_retry(user_id, message) for user_id in recipients]
        await asyncio.gather(*tasks)

    async def _get_students_without_weekly_report(self):
        users = await self.db.get_all_active_users()
        result = []
        for user in users:
            reports = await self.db.get_reports_for_current_week(user['user_id'])
            if not reports:
                result.append(user['user_id'])
        return result

    async def _send_with_retry(self, user_id, message, retry_delay=300):
        while True:
            try:
                await self.bot.send_message(user_id, message)
                return
            except Exception as error:
                if not self._should_retry(error):
                    logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {error}")
                    return
                logger.warning(f"Повторная попытка отправки сообщения пользователю {user_id}: {error}")
                await asyncio.sleep(retry_delay)

    def _should_retry(self, error):
        text = str(error).lower()
        fatal_markers = (
            "blocked",
            "forbidden",
            "chat not found",
            "user is deactivated",
            "bot was kicked",
        )
        return not any(marker in text for marker in fatal_markers)

    async def send_curator_missing_reports_notifications(self):
        """Отправляет кураторам уведомления о неотправленных отчетах их учеников"""
        missing_records = await self.db.get_students_missing_weekly_reports()
        if not missing_records:
            return

        def build_name(first_name, last_name, username, fallback_id):
            if first_name and last_name:
                return escape_markdown(f"{first_name} {last_name}")
            if username:
                return escape_markdown(username)
            return escape_markdown(f"ID: {fallback_id}")

        students_by_curator = {}
        for record in missing_records:
            curator_id = record['curator_id']
            student_name = build_name(
                record['student_first_name'],
                record['student_last_name'],
                record['student_username'],
                record['student_id']
            )
            students_by_curator.setdefault(curator_id, []).append(student_name)

        for curator_id, students in students_by_curator.items():
            students_list = "\n".join([f"• {name}" for name in students])
            try:
                await self.bot.send_message(
                    curator_id,
                    f"⚠️ *Уведомление куратора*\n\n"
                    f"Следующие ученики не отправили отчет за эту неделю:\n\n"
                    f"{students_list}\n\n"
                    f"Рекомендуется связаться с ними для выяснения причин."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление куратору {curator_id}: {e}")
