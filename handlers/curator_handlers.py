from datetime import datetime
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from states import CuratorStates
from database import Database
from notifications import NotificationService

def register_curator_handlers(dp: Dispatcher, db: Database, notification_service: NotificationService):
    
    # Создаем клавиатуру для кураторов
    curator_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Добавить ученика"), KeyboardButton(text="👥 Мои ученики")],
            [KeyboardButton(text="📋 Все ученики"), KeyboardButton(text="📝 Отчеты")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    BACK_BUTTON_TEXT = "⬅️ Назад"

    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BACK_BUTTON_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    async def handle_back_navigation(message: Message, state: FSMContext) -> bool:
        if message.text == BACK_BUTTON_TEXT:
            await state.clear()
            await message.answer("↩️ Возвращаю режим куратора.", reply_markup=curator_keyboard)
            return True
        return False
    
    @dp.message(Command("curator"))
    async def curator_handler(message: Message):
        user = message.from_user
        user_id = user.id
        
        # Проверяем права доступа
        is_admin = await db.is_admin(user_id)
        current_user_type = await db.get_user_type(user_id)
        
        if not is_admin and current_user_type != 'curator':
            await message.answer(
                "❌ *Доступ запрещен!*\n\n"
                "У тебя нет прав для использования режима куратора.\n"
                "Обратитесь к администратору для получения доступа."
            )
            return
        
        await db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            user_type='curator'
        )
        
        await message.answer(
            "👨‍🏫 *Режим куратора активирован!*\n\n"
            "Используй кнопки ниже для навигации:",
            reply_markup=curator_keyboard
        )

    @dp.message(Command("add_student"))
    async def add_student_handler(message: Message, state: FSMContext):
        await state.set_state(CuratorStates.waiting_for_student_id)
        await message.answer(
            "👤 *Добавление ученика*\n\n"
            "Отправь ID ученика (число), которого хочешь добавить к себе.\n"
            "Ученик должен сначала зарегистрироваться через /start.\n\n"
            f"Для возврата нажми '{BACK_BUTTON_TEXT}'.",
            reply_markup=back_keyboard
        )

    @dp.message(CuratorStates.waiting_for_student_id)
    async def process_student_id(message: Message, state: FSMContext):
        if await handle_back_navigation(message, state):
            return

        try:
            student_id = int(message.text)
        except ValueError:
            await message.answer("❌ Пожалуйста, отправь корректный ID ученика (число).", reply_markup=back_keyboard)
            return

        curator_id = message.from_user.id

        await db.add_curator_student_relation(curator_id, student_id)
        await state.clear()

        await message.answer(
            f"✅ Ученик с ID {student_id} добавлен к тебе!\n"
            f"Теперь ты будешь получать уведомления о его отчетах.",
            reply_markup=curator_keyboard
        )
        
        await notification_service.notify_student_curator_assigned(student_id)

    @dp.message(Command("my_students"))
    async def my_students_handler(message: Message):
        curator_id = message.from_user.id
        students = await db.get_curator_students(curator_id)
        
        if not students:
            await message.answer("У тебя пока нет учеников. Используй /add_student для добавления.")
            return
        
        response = "👥 *Твои ученики:*\n\n"
        for student in students:
            name = f"{student['first_name']} {student['last_name']}" if student['first_name'] and student['last_name'] else student['username'] or f"ID: {student['user_id']}"
            response += f"• {name} (ID: {student['user_id']})\n"
        
        await message.answer(response)

    @dp.message(Command("all_students"))
    async def all_students_handler(message: Message):
        students = await db.get_all_students_with_curators()
        
        if not students:
            await message.answer("В системе пока нет учеников.")
            return
        
        response = "👥 *Все ученики и их кураторы:*\n\n"
        
        for student in students:
            # Формируем имя ученика
            student_name = f"{student['first_name']} {student['last_name']}" if student['first_name'] and student['last_name'] else student['username'] or f"ID: {student['user_id']}"
            
            # Формируем имя куратора
            if student['curator_id']:
                curator_name = f"{student['curator_first_name']} {student['curator_last_name']}" if student['curator_first_name'] and student['curator_last_name'] else student['curator_username'] or f"ID: {student['curator_id']}"
                curator_status = f"👨‍🏫 {curator_name}"
            else:
                curator_status = "❌ Без куратора"
            
            response += f"*{student_name}* (ID: {student['user_id']})\n"
            response += f"   {curator_status}\n\n"
        
        # Добавляем статистику
        total_students = len(students)
        with_curators = len([s for s in students if s['curator_id']])
        without_curators = total_students - with_curators
        
        response += f"📊 *Статистика:*\n"
        response += f"Всего учеников: {total_students}\n"
        response += f"С кураторами: {with_curators}\n"
        response += f"Без кураторов: {without_curators}"
        
        await message.answer(response)

    @dp.message(Command("reports"))
    async def reports_handler(message: Message):
        curator_id = message.from_user.id
        reports = await db.get_unread_reports_for_curator(curator_id)
        
        if not reports:
            await message.answer("📭 У тебя нет непрочитанных отчетов.")
            return
        
        for report in reports[:5]:  # Показываем максимум 5 отчетов
            date = datetime.fromisoformat(report['created_at']).strftime('%d.%m.%Y %H:%M')
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Отметить как прочитанный", callback_data=f"read_{report['id']}")]
            ])
            
            await message.answer(
                f"📝 *Отчет от {report['student_name']}*\n"
                f"📅 {date}\n\n"
                f"🎯 *Этап:* {report['current_stage']}\n"
                f"📋 *Планы:* {report['plans']}\n"
                f"❓ *Проблемы:* {report['problems']}",
                reply_markup=keyboard
            )
        
        if len(reports) > 5:
            await message.answer(f"... и еще {len(reports) - 5} отчетов")

    @dp.callback_query(lambda c: c.data.startswith('read_'))
    async def mark_report_read(callback: CallbackQuery):
        report_id = int(callback.data.split('_')[1])
        curator_id = callback.from_user.id
        
        await db.mark_report_as_read(report_id, curator_id)
        
        # Получаем информацию об отчете для уведомления ученика
        report = await db.get_report_by_id(report_id)
        if report:
            await notification_service.notify_student_report_read(report['user_id'], report)
        
        await callback.answer("✅ Отчет отмечен как прочитанный!")
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ *ПРОЧИТАНО*",
            reply_markup=None
        )

    # Обработчики кнопок для кураторов
    @dp.message(lambda message: message.text == "👤 Добавить ученика")
    async def button_add_student_handler(message: Message, state: FSMContext):
        await add_student_handler(message, state)

    @dp.message(lambda message: message.text == "👥 Мои ученики")
    async def button_my_students_handler(message: Message):
        await my_students_handler(message)

    @dp.message(lambda message: message.text == "📋 Все ученики")
    async def button_all_students_handler(message: Message):
        await all_students_handler(message)

    @dp.message(lambda message: message.text == "📝 Отчеты")
    async def button_reports_handler(message: Message):
        await reports_handler(message)

    @dp.message(lambda message: message.text == "❓ Помощь")
    async def button_help_handler(message: Message):
        from bot import get_role_based_help
        help_text, keyboard = await get_role_based_help(message.from_user.id)
        await message.answer(help_text, reply_markup=keyboard)
