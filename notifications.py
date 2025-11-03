import logging
from datetime import datetime
from typing import Optional
from aiogram import Bot
from database import Database

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db

    def _format_user_name(self, user: Optional[dict], fallback_id: int) -> str:
        if not user:
            return f"ID: {fallback_id}"
        first_name = user.get('first_name')
        last_name = user.get('last_name')
        if first_name and last_name:
            return f"{first_name} {last_name}"
        username = user.get('username')
        if username:
            return username
        return f"ID: {fallback_id}"

    async def notify_curator_new_report(self, student_id: int, report_data: dict):
        """Уведомляет куратора о новом отчете от ученика"""
        curator = await self.db.get_student_curator(student_id)
        if not curator:
            return
        student_profile = await self.db.get_user_profile(student_id)
        student_name = self._format_user_name(student_profile, student_id)
        
        try:
            await self.bot.send_message(
                curator['user_id'],
                f"📝 *Новый отчет от {student_name}!*\n\n"
                f"🎯 *Этап:* {report_data['current_stage']}\n"
                f"📋 *Планы:* {report_data['plans']}\n"
                f"❓ *Проблемы:* {report_data['problems']}\n\n"
                f"Используйте /reports для просмотра всех отчетов."
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
            await self.bot.send_message(
                student_id,
                "✅ *Твой отчет просмотрен куратором!*\n\n"
                f"🎯 *Этап:* {report_data['current_stage']}\n"
                f"📋 *Планы:* {report_data['plans']}\n"
                f"❓ *Проблемы:* {report_data['problems']}"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить ученика {student_id}: {e}")

    async def send_weekly_reminders(self):
        """Отправляет еженедельные напоминания ученикам"""
        users = await self.db.get_all_active_users()
        
        for user in users:
            # Проверяем, есть ли отчет за текущую неделю
            current_week_reports = await self.db.get_reports_for_current_week(user['user_id'])
            
            # Отправляем напоминание только если нет отчета за текущую неделю
            if not current_week_reports:
                try:
                    await self.bot.send_message(
                        user['user_id'],
                        "📝 *Время для еженедельного отчета!*\n\n"
                        "Пожалуйста, заполни отчет по форме:\n"
                        "• На каком сейчас этапе? (этап + тема)\n"
                        "• Что планируешь делать?\n"
                        "• Есть ли проблемы или вопросы?\n\n"
                        "Используй кнопку '📝 Отправить отчет' для начала заполнения."
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение пользователю {user['user_id']}: {e}")

    async def send_curator_missing_reports_notifications(self):
        """Отправляет кураторам уведомления о неотправленных отчетах их учеников"""
        missing_records = await self.db.get_students_missing_weekly_reports()
        if not missing_records:
            return

        def build_name(first_name, last_name, username, fallback_id):
            if first_name and last_name:
                return f"{first_name} {last_name}"
            if username:
                return username
            return f"ID: {fallback_id}"

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
