from datetime import datetime
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from states import CuratorStates
from database import Database
from notifications import NotificationService
from text_utils import escape_markdown

def register_curator_handlers(dp: Dispatcher, db: Database, notification_service: NotificationService):
    
    def format_report_text(report: dict, index: int) -> str:
        date = datetime.fromisoformat(report['created_at']).strftime('%d.%m.%Y %H:%M')
        read_status = "✅ Прочитано" if report['is_read_by_curator'] else "📭 Не прочитано"
        
        text = f"*{index}. {date}* {read_status}\n"
        stage = escape_markdown(report['current_stage'])
        plans = escape_markdown(report['plans'])
        text += f"🎯 *Этап:* {stage}\n"
        text += f"📋 *Планы:* {plans}\n"
        
        if report['plans_completed'] is not None:
            if report['plans_completed']:
                text += f"✅ *Выполнение планов:* Да\n"
            else:
                text += f"❌ *Выполнение планов:* Нет\n"
                if report['plans_failure_reason']:
                    failure_reason = escape_markdown(report['plans_failure_reason'])
                    text += f"📝 *Причина:* {failure_reason}\n"
        
        problems = escape_markdown(report['problems'])
        text += f"❓ *Проблемы:* {problems}\n\n"
        return text
    
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
            await message.answer("У тебя пока нет учеников. Используй команду `/add_student` для добавления.")
            return
        
        response = "👥 *Твои ученики:*\n\n"
        keyboard_buttons = []
        
        for student in students:
            name = f"{student['first_name']} {student['last_name']}" if student['first_name'] and student['last_name'] else student['username'] or f"ID: {student['user_id']}"
            display_name = escape_markdown(name)
            response += f"• {display_name} (ID: {student['user_id']})\n"
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"📋 Отчеты {name}",
                callback_data=f"view_reports_{student['user_id']}"
            )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer(response, reply_markup=keyboard)

    @dp.message(Command("all_students"))
    async def all_students_handler(message: Message):
        students = await db.get_all_students_with_curators()
        
        if not students:
            await message.answer("В системе пока нет учеников.")
            return
        
        response = "👥 *Все ученики и их кураторы:*\n\n"
        
        for student in students:
            student_name_raw = f"{student['first_name']} {student['last_name']}" if student['first_name'] and student['last_name'] else student['username'] or f"ID: {student['user_id']}"
            student_name = escape_markdown(student_name_raw)
            
            if student['curator_id']:
                curator_name_raw = f"{student['curator_first_name']} {student['curator_last_name']}" if student['curator_first_name'] and student['curator_last_name'] else student['curator_username'] or f"ID: {student['curator_id']}"
                curator_name = escape_markdown(curator_name_raw)
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
            student_name = escape_markdown(report['student_name'])
            report_stage = escape_markdown(report['current_stage'])
            report_plans = escape_markdown(report['plans'])
            report_problems = escape_markdown(report['problems'])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Отметить как прочитанный", callback_data=f"read_{report['id']}")]
            ])
            
            await message.answer(
                f"📝 *Отчет от {student_name}*\n"
                f"📅 {date}\n\n"
                f"🎯 *Этап:* {report_stage}\n"
                f"📋 *Планы:* {report_plans}\n"
                f"❓ *Проблемы:* {report_problems}",
                reply_markup=keyboard
            )
        
        if len(reports) > 5:
            await message.answer(f"... и еще {len(reports) - 5} отчетов")

    @dp.callback_query(lambda c: c.data.startswith('read_'))
    async def mark_report_read(callback: CallbackQuery):
        report_id = int(callback.data.split('_')[1])
        curator_id = callback.from_user.id
        
        await db.mark_report_as_read(report_id, curator_id)
        
        report = await db.get_report_by_id(report_id)
        if report:
            await notification_service.notify_student_report_read(report['user_id'], report)
        
        await callback.answer("✅ Отчет отмечен как прочитанный!")
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ *ПРОЧИТАНО*",
            reply_markup=None
        )

    @dp.callback_query(lambda c: c.data.startswith('view_reports_'))
    async def view_student_reports(callback: CallbackQuery):
        student_id = int(callback.data.split('_')[2])
        curator_id = callback.from_user.id
        
        reports = await db.get_all_student_reports_for_curator(curator_id, student_id)
        
        if not reports:
            await callback.answer("У этого ученика пока нет отчетов.")
            return
        
        student_name_raw = reports[0]['student_name'] if reports else f"ID: {student_id}"
        student_name = escape_markdown(student_name_raw)
        header = f"📋 *Все отчеты ученика {student_name}:*\n\n"
        
        response = header
        for i, report in enumerate(reports, 1):
            response += format_report_text(report, i)
        
        response += f"📊 *Всего отчетов:* {len(reports)}"
        
        if len(response) > 4096:
            chunks = []
            current_chunk = header
            
            for i, report in enumerate(reports, 1):
                report_text = format_report_text(report, i)
                
                if len(current_chunk) + len(report_text) > 4000:
                    chunks.append(current_chunk)
                    current_chunk = report_text
                else:
                    current_chunk += report_text
            
            if current_chunk:
                current_chunk += f"\n📊 *Всего отчетов:* {len(reports)}"
                chunks.append(current_chunk)
            
            for chunk in chunks:
                await callback.message.answer(chunk)
        else:
            await callback.message.answer(response)
        
        await callback.answer()

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
