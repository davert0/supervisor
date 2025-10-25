import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from database import Database
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

@dp.message(Command("start"))
async def start_handler(message: Message):
    user = message.from_user
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    await message.answer(
        "Привет! Я бот для сбора еженедельных отчетов.\n\n"
        "Команды:\n"
        "/report - отправить отчет\n"
        "/my_reports - посмотреть мои отчеты\n"
        "/help - помощь"
    )

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Доступные команды:\n\n"
        "/start - регистрация в системе\n"
        "/report - отправить отчет\n"
        "/my_reports - посмотреть мои отчеты\n"
        "/help - показать это сообщение\n\n"
        "Я буду напоминать вам каждую неделю о необходимости отправить отчет."
    )

@dp.message(Command("report"))
async def report_handler(message: Message):
    await message.answer(
        "Пожалуйста, напишите ваш еженедельный отчет. "
        "Опишите что вы изучили, какие задачи выполнили, "
        "с какими трудностями столкнулись и что планируете на следующую неделю."
    )

@dp.message(Command("my_reports"))
async def my_reports_handler(message: Message):
    user_id = message.from_user.id
    reports = await db.get_user_reports(user_id)
    
    if not reports:
        await message.answer("У вас пока нет отчетов.")
        return
    
    response = "Ваши отчеты:\n\n"
    for i, report in enumerate(reports[:10], 1):
        date = datetime.fromisoformat(report['created_at']).strftime('%d.%m.%Y %H:%M')
        text = report['text'][:100] + "..." if len(report['text']) > 100 else report['text']
        response += f"{i}. {date}\n{text}\n\n"
    
    if len(reports) > 10:
        response += f"... и еще {len(reports) - 10} отчетов"
    
    await message.answer(response)

@dp.message(F.text)
async def text_handler(message: Message):
    user_id = message.from_user.id
    text = message.text
    
    if len(text) < 10:
        await message.answer(
            "Отчет слишком короткий. Пожалуйста, напишите более подробный отчет "
            "(минимум 10 символов)."
        )
        return
    
    await db.save_report(user_id, text)
    await message.answer(
        "✅ Отчет сохранен! Спасибо за вашу работу. "
        "Следующее напоминание придет через неделю."
    )

async def send_weekly_reminders():
    while True:
        try:
            users = await db.get_all_active_users()
            current_time = datetime.now()
            
            for user in users:
                last_report = await db.get_last_report_date(user['user_id'])
                
                if last_report is None or (current_time - last_report).days >= 7:
                    try:
                        await bot.send_message(
                            user['user_id'],
                            "📝 Время для еженедельного отчета!\n\n"
                            "Пожалуйста, напишите что вы изучили на этой неделе, "
                            "какие задачи выполнили и с какими трудностями столкнулись. "
                            "Используйте команду /report для отправки отчета."
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение пользователю {user['user_id']}: {e}")
            
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            await asyncio.sleep(3600)

async def main():
    await db.init_db()
    
    reminder_task = asyncio.create_task(send_weekly_reminders())
    
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
