import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from database import Database
from notifications import NotificationService
from scheduler import Scheduler
from handlers.student_handlers import register_student_handlers
from handlers.curator_handlers import register_curator_handlers
from handlers.admin_handlers import register_admin_handlers
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()
notification_service = NotificationService(bot, db)
scheduler = Scheduler(notification_service)

register_student_handlers(dp, db, notification_service)
register_curator_handlers(dp, db, notification_service)
register_admin_handlers(dp, db, notification_service)

async def get_role_based_help(user_id: int) -> tuple[str, ReplyKeyboardMarkup]:
    """Возвращает help-сообщение и клавиатуру в зависимости от роли пользователя"""
    is_admin = await db.is_admin(user_id)
    user_type = await db.get_user_type(user_id)
    
    if is_admin:
        help_text = (
            "🔧 *Команды администратора:*\n\n"
            "/admin - панель администратора\n"
            "/all_curators - все кураторы\n"
            "/all_students_admin - все ученики\n"
            "/notify_curators - уведомить кураторов о неотправленных отчетах\n"
            "/add_curator - добавить куратора\n"
            "/assign_student - назначить ученика куратору\n"
            "/remove_relation - удалить связь\n"
            "/deactivate_curator - деактивировать куратора\n"
            "/activate_curator - активировать куратора\n"
            "/students_without_curators - ученики без кураторов\n"
            "/admin_stats - статистика\n"
            "/help - помощь"
        )
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👥 Все кураторы"), KeyboardButton(text="👥 Все ученики")],
                [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👤 Добавить куратора")],
                [KeyboardButton(text="🔗 Назначить ученика"), KeyboardButton(text="❌ Удалить связь")],
                [KeyboardButton(text="🚫 Деактивировать куратора"), KeyboardButton(text="✅ Активировать куратора")],
                [KeyboardButton(text="👥 Без кураторов"), KeyboardButton(text="❓ Помощь админа")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    elif user_type == 'curator':
        help_text = (
            "👨‍🏫 *Команды куратора:*\n\n"
            "/curator - активация режима куратора\n"
            "/add_student - добавить ученика\n"
            "/my_students - мои ученики\n"
            "/all_students - все ученики и их кураторы\n"
            "/reports - непрочитанные отчеты\n"
            "/help - помощь"
        )
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 Добавить ученика"), KeyboardButton(text="👥 Мои ученики")],
                [KeyboardButton(text="📋 Все ученики"), KeyboardButton(text="📝 Отчеты")],
                [KeyboardButton(text="❓ Помощь")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    else:
        help_text = (
            "📝 *Команды ученика:*\n\n"
            "/start - регистрация в системе\n"
            "/report - отправить отчет\n"
            "/my_reports - посмотреть мои отчеты\n"
            "/help - помощь"
        )
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📝 Отправить отчет"), KeyboardButton(text="📊 Мои отчеты")],
                [KeyboardButton(text="❓ Помощь")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    return help_text, keyboard

# Обработчик случайных сообщений
@dp.message()
async def random_message_handler(message):
    user_id = message.from_user.id
    
    help_text, keyboard = await get_role_based_help(user_id)
    await message.answer(help_text, reply_markup=keyboard)

# Обработчик команды /help
@dp.message(Command("help"))
async def help_handler(message: Message):
    user_id = message.from_user.id
    help_text, keyboard = await get_role_based_help(user_id)
    await message.answer(help_text, reply_markup=keyboard)

async def main():
    await db.init_db()
    
    reminder_task = asyncio.create_task(scheduler.start_weekly_reminders())
    
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
