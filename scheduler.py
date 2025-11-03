import asyncio
import logging
from datetime import datetime
from notifications import NotificationService

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    async def start_weekly_reminders(self):
        """Запускает планировщик еженедельных напоминаний"""
        while True:
            try:
                current_time = datetime.now()
                current_weekday = current_time.weekday()  # 0 = понедельник, 2 = среда
                current_hour = current_time.hour
                
                if current_weekday == 0 and current_hour == 10:
                    await self.notification_service.send_weekly_reminders()
                    logger.info("Отправлены еженедельные напоминания ученикам")
                if current_weekday in {1, 2, 3, 4, 5, 6} and current_hour == 10:
                    await self.notification_service.send_daily_missing_report_reminders()
                    logger.info("Отправлены ежедневные напоминания ученикам без отчета")
                
                if current_weekday == 2 and current_hour == 14:
                    await self.notification_service.send_curator_missing_reports_notifications()
                    logger.info("Отправлены уведомления кураторам о неотправленных отчетах")
                
                await asyncio.sleep(3600)  # Проверяем каждый час
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                await asyncio.sleep(3600)
