from datetime import datetime
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from states import AdminStates
from database import Database
from notifications import NotificationService

def register_admin_handlers(dp: Dispatcher, db: Database, notification_service: NotificationService):
    
    admin_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Все кураторы"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="👤 Добавить куратора"), KeyboardButton(text="🔗 Назначить ученика")],
            [KeyboardButton(text="❌ Удалить связь"), KeyboardButton(text="🚫 Деактивировать куратора")],
            [KeyboardButton(text="✅ Активировать куратора"), KeyboardButton(text="👥 Без кураторов")],
            [KeyboardButton(text="❓ Помощь админа")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    async def check_admin_access(message: Message) -> bool:
        if not await db.is_admin(message.from_user.id):
            await message.answer("❌ У тебя нет прав администратора!")
            return False
        return True

    @dp.message(Command("admin"))
    async def admin_handler(message: Message):
        if not await check_admin_access(message):
            return
            
        await message.answer(
            "🔧 *Панель администратора кураторов*\n\n"
            "Используйте кнопки ниже для управления кураторами:",
            reply_markup=admin_keyboard
        )

    @dp.message(Command("all_curators"))
    async def all_curators_handler(message: Message):
        if not await check_admin_access(message):
            return
            
        curators = await db.get_all_curators()
        
        if not curators:
            await message.answer("В системе нет кураторов.")
            return
        
        response = "👥 *Все кураторы:*\n\n"
        
        for curator in curators:
            stats = await db.get_curator_stats(curator['user_id'])
            name = f"{curator['first_name']} {curator['last_name']}" if curator['first_name'] and curator['last_name'] else curator['username'] or f"ID: {curator['user_id']}"
            
            response += f"*{name}* (ID: {curator['user_id']})\n"
            response += f"   👥 Учеников: {stats['student_count']}\n"
            response += f"   📝 Отчетов: {stats['total_reports']}\n"
            response += f"   📭 Непрочитанных: {stats['unread_reports']}\n\n"
        
        await message.answer(response)

    @dp.message(Command("add_curator"))
    async def add_curator_handler(message: Message, state: FSMContext):
        if not await check_admin_access(message):
            return
            
        await state.set_state(AdminStates.waiting_for_curator_id)
        await message.answer(
            "👤 *Добавление куратора*\n\n"
            "Отправьте ID пользователя, которого хотите сделать куратором.\n"
            "Пользователь должен быть зарегистрирован в системе."
        )

    @dp.message(AdminStates.waiting_for_curator_id)
    async def process_curator_id(message: Message, state: FSMContext):
        try:
            curator_id = int(message.text)
            
            await db.add_user(
                user_id=curator_id,
                user_type='curator'
            )
            await state.clear()
            
            await message.answer(
                f"✅ Пользователь с ID {curator_id} назначен куратором!\n"
                f"Теперь он может использовать команду /curator для активации режима куратора."
            )
            
        except ValueError:
            await message.answer("❌ Пожалуйста, отправьте корректный ID пользователя (число).")

    @dp.message(Command("assign_student"))
    async def assign_student_handler(message: Message, state: FSMContext):
        if not await check_admin_access(message):
            return
            
        students = await db.get_students_without_curators()
        curators = await db.get_all_curators()
        
        if not students:
            await message.answer("Все ученики уже имеют кураторов.")
            return
            
        if not curators:
            await message.answer("В системе нет кураторов. Сначала добавьте кураторов.")
            return
        
        await state.set_state(AdminStates.waiting_for_student_to_assign)
        await state.update_data(curators=curators)
        
        response = "👥 *Выбери ученика для назначения куратора:*\n\n"
        for i, student in enumerate(students[:10], 1):
            name = f"{student['first_name']} {student['last_name']}" if student['first_name'] and student['last_name'] else student['username'] or f"ID: {student['user_id']}"
            response += f"{i}. {name} (ID: {student['user_id']})\n"
        
        if len(students) > 10:
            response += f"... и еще {len(students) - 10} учеников\n"
        
        response += "\nОтправьте номер ученика:"
        await message.answer(response)

    @dp.message(AdminStates.waiting_for_student_to_assign)
    async def process_student_selection(message: Message, state: FSMContext):
        try:
            student_num = int(message.text)
            data = await state.get_data()
            students = await db.get_students_without_curators()
            
            if 1 <= student_num <= len(students):
                student = students[student_num - 1]
                await state.update_data(selected_student=student)
                await state.set_state(AdminStates.waiting_for_curator_to_assign)
                
                curators = data['curators']
                response = f"👤 *Выбран ученик:* {student['first_name']} {student['last_name']} (ID: {student['user_id']})\n\n"
                response += "👥 *Выбери куратора из списка ниже:*\n\n"
                
                for i, curator in enumerate(curators, 1):
                    name = f"{curator['first_name']} {curator['last_name']}" if curator['first_name'] and curator['last_name'] else curator['username'] or f"ID: {curator['user_id']}"
                    response += f"{i}. {name} (ID: {curator['user_id']})\n"
                
                response += "\nОтправьте номер куратора:"
                await message.answer(response)
            else:
                await message.answer("❌ Неверный номер ученика. Попробуйте снова.")
                
        except ValueError:
            await message.answer("❌ Пожалуйста, отправьте корректный номер ученика.")

    @dp.message(AdminStates.waiting_for_curator_to_assign)
    async def process_curator_selection(message: Message, state: FSMContext):
        try:
            curator_num = int(message.text)
            data = await state.get_data()
            curators = data['curators']
            student = data['selected_student']
            
            if 1 <= curator_num <= len(curators):
                curator = curators[curator_num - 1]
                
                await db.assign_student_to_curator(student['user_id'], curator['user_id'])
                await state.clear()
                
                await message.answer(
                    f"✅ *Назначение выполнено!*\n\n"
                    f"👤 Ученик: {student['first_name']} {student['last_name']} (ID: {student['user_id']})\n"
                    f"👨‍🏫 Куратор: {curator['first_name']} {curator['last_name']} (ID: {curator['user_id']})\n\n"
                    f"Теперь куратор будет получать уведомления об отчетах этого ученика."
                )
                
                await notification_service.notify_student_curator_assigned(student['user_id'])
            else:
                await message.answer("❌ Неверный номер куратора. Попробуйте снова.")
                
        except ValueError:
            await message.answer("❌ Пожалуйста, отправьте корректный номер куратора.")

    @dp.message(Command("remove_relation"))
    async def remove_relation_handler(message: Message, state: FSMContext):
        if not await check_admin_access(message):
            return
            
        await state.set_state(AdminStates.waiting_for_student_id)
        await message.answer(
            "🔗 *Удаление связи куратор-ученик*\n\n"
            "Отправьте ID ученика, у которого нужно удалить связь с куратором."
        )

    @dp.message(AdminStates.waiting_for_student_id)
    async def process_remove_relation(message: Message, state: FSMContext):
        try:
            student_id = int(message.text)
            curator = await db.get_student_curator(student_id)
            
            if curator:
                await db.remove_curator_student_relation(curator['user_id'], student_id)
                await state.clear()
                
                await message.answer(
                    f"✅ Связь с куратором удалена для ученика ID {student_id}.\n"
                    f"Куратор: {curator['first_name']} {curator['last_name']}"
                )
            else:
                await message.answer(f"❌ У ученика ID {student_id} нет куратора.")
                
        except ValueError:
            await message.answer("❌ Пожалуйста, отправьте корректный ID ученика (число).")

    @dp.message(Command("deactivate_curator"))
    async def deactivate_curator_handler(message: Message, state: FSMContext):
        if not await check_admin_access(message):
            return
            
        await state.set_state(AdminStates.waiting_for_curator_id)
        await message.answer(
            "🚫 *Деактивация куратора*\n\n"
            "Отправьте ID куратора, которого нужно деактивировать."
        )

    @dp.message(AdminStates.waiting_for_curator_id)
    async def process_deactivate_curator(message: Message, state: FSMContext):
        try:
            curator_id = int(message.text)
            
            await db.deactivate_curator(curator_id)
            await state.clear()
            
            await message.answer(f"✅ Куратор ID {curator_id} деактивирован.")
                
        except ValueError:
            await message.answer("❌ Пожалуйста, отправьте корректный ID куратора (число).")

    @dp.message(Command("activate_curator"))
    async def activate_curator_handler(message: Message, state: FSMContext):
        if not await check_admin_access(message):
            return
            
        await state.set_state(AdminStates.waiting_for_curator_id)
        await message.answer(
            "✅ *Активация куратора*\n\n"
            "Отправьте ID куратора, которого нужно активировать."
        )

    @dp.message(Command("students_without_curators"))
    async def students_without_curators_handler(message: Message):
        if not await check_admin_access(message):
            return
            
        students = await db.get_students_without_curators()
        
        if not students:
            await message.answer("✅ Все ученики имеют кураторов.")
            return
        
        response = "👥 *Ученики без кураторов:*\n\n"
        for student in students:
            name = f"{student['first_name']} {student['last_name']}" if student['first_name'] and student['last_name'] else student['username'] or f"ID: {student['user_id']}"
            response += f"• {name} (ID: {student['user_id']})\n"
        
        response += f"\n📊 Всего без кураторов: {len(students)}"
        await message.answer(response)

    @dp.message(Command("admin_stats"))
    async def admin_stats_handler(message: Message):
        if not await check_admin_access(message):
            return
            
        curators = await db.get_all_curators()
        students_with_curators = await db.get_all_students_with_curators()
        students_without_curators = await db.get_students_without_curators()
        
        total_curators = len(curators)
        total_students = len(students_with_curators) + len(students_without_curators)
        students_with_curators_count = len([s for s in students_with_curators if s['curator_id']])
        
        response = "📊 *Общая статистика системы:*\n\n"
        response += f"👨‍🏫 Всего кураторов: {total_curators}\n"
        response += f"👥 Всего учеников: {total_students}\n"
        response += f"🔗 С кураторами: {students_with_curators_count}\n"
        response += f"❌ Без кураторов: {len(students_without_curators)}\n\n"
        
        if curators:
            response += "📈 *Статистика по кураторам:*\n"
            for curator in curators[:5]:
                stats = await db.get_curator_stats(curator['user_id'])
                name = f"{curator['first_name']} {curator['last_name']}" if curator['first_name'] and curator['last_name'] else curator['username'] or f"ID: {curator['user_id']}"
                response += f"• {name}: {stats['student_count']} учеников, {stats['unread_reports']} непрочитанных\n"
            
            if len(curators) > 5:
                response += f"... и еще {len(curators) - 5} кураторов"
        
        await message.answer(response)

    @dp.message(Command("all_students_admin"))
    async def all_students_admin_handler(message: Message):
        if not await check_admin_access(message):
            return
            
        students = await db.get_all_students_with_curators()
        
        if not students:
            await message.answer("В системе нет учеников.")
            return
        
        response = "👥 *Все ученики в системе:*\n\n"
        
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

    @dp.message(lambda message: message.text == "👥 Все кураторы")
    async def button_all_curators_handler(message: Message):
        await all_curators_handler(message)

    @dp.message(lambda message: message.text == "📊 Статистика")
    async def button_admin_stats_handler(message: Message):
        await admin_stats_handler(message)

    @dp.message(lambda message: message.text == "👤 Добавить куратора")
    async def button_add_curator_handler(message: Message, state: FSMContext):
        await add_curator_handler(message, state)

    @dp.message(lambda message: message.text == "🔗 Назначить ученика")
    async def button_assign_student_handler(message: Message, state: FSMContext):
        await assign_student_handler(message, state)

    @dp.message(lambda message: message.text == "❌ Удалить связь")
    async def button_remove_relation_handler(message: Message, state: FSMContext):
        await remove_relation_handler(message, state)

    @dp.message(lambda message: message.text == "🚫 Деактивировать куратора")
    async def button_deactivate_curator_handler(message: Message, state: FSMContext):
        await deactivate_curator_handler(message, state)

    @dp.message(lambda message: message.text == "✅ Активировать куратора")
    async def button_activate_curator_handler(message: Message, state: FSMContext):
        await activate_curator_handler(message, state)

    @dp.message(lambda message: message.text == "👥 Без кураторов")
    async def button_students_without_curators_handler(message: Message):
        await students_without_curators_handler(message)

    @dp.message(lambda message: message.text == "👥 Все ученики")
    async def button_all_students_admin_handler(message: Message):
        await all_students_admin_handler(message)

    @dp.message(lambda message: message.text == "❓ Помощь админа")
    async def button_admin_help_handler(message: Message):
        from bot import get_role_based_help
        help_text, keyboard = await get_role_based_help(message.from_user.id)
        await message.answer(help_text, reply_markup=keyboard)

    @dp.message(Command("notify_curators"))
    async def notify_curators_handler(message: Message):
        """Ручной запуск уведомлений кураторам о неотправленных отчетах"""
        if not await check_admin_access(message):
            return
            
        try:
            await notification_service.send_curator_missing_reports_notifications()
            await message.answer("✅ Уведомления кураторам о неотправленных отчетах отправлены!")
        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке уведомлений: {e}")
