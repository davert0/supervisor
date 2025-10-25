import logging
from datetime import datetime
from aiogram import Bot
from database import Database

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db

    async def notify_curator_new_report(self, student_id: int, report_data: dict):
        """Уведомляет куратора о новом отчете от ученика"""
        curator = await self.db.get_student_curator(student_id)
        if not curator:
            return
        
        try:
            await self.bot.send_message(
                curator['user_id'],
                f"📝 *Новый отчет от ученика!*\n\n"
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
        curators = await self.db.get_all_curators()
        
        for curator in curators:
            students = await self.db.get_curator_students(curator['user_id'])
            missing_reports_students = []
            
            for student in students:
                # Проверяем, есть ли отчет за текущую неделю
                current_week_reports = await self.db.get_reports_for_current_week(student['user_id'])
                
                if not current_week_reports:
                    # Формируем имя студента
                    student_name = f"{student['first_name']} {student['last_name']}" if student['first_name'] and student['last_name'] else student['username'] or f"ID: {student['user_id']}"
                    missing_reports_students.append(student_name)
            
            # Отправляем уведомление куратору, если есть студенты без отчетов
            if missing_reports_students:
                try:
                    students_list = "\n".join([f"• {name}" for name in missing_reports_students])
                    await self.bot.send_message(
                        curator['user_id'],
                        f"⚠️ *Уведомление куратора*\n\n"
                        f"Следующие ученики не отправили отчет за эту неделю:\n\n"
                        f"{students_list}\n\n"
                        f"Рекомендуется связаться с ними для выяснения причин."
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление куратору {curator['user_id']}: {e}")
