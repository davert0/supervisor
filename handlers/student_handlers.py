from datetime import datetime
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states import ReportStates
from database import Database
from notifications import NotificationService
from text_utils import escape_markdown

STAGE_OPTIONS = [
    (
        "stage_block1",
        "📚 Изучение материалов - Блок 1. Основы языка",
        "Изучение материалов - Блок 1. Основы языка"
    ),
    (
        "stage_block2",
        "📚 Изучение материалов - Блок 2. ООП",
        "Изучение материалов - Блок 2. ООП"
    ),
    (
        "stage_block3",
        "📚 Изучение материалов - Блок 3. Конкурентность",
        "Изучение материалов - Блок 3. Конкурентность"
    ),
    (
        "stage_block4",
        "📚 Изучение материалов - Блок 4. Инфраструктура",
        "Изучение материалов - Блок 4. Инфраструктура"
    ),
    (
        "stage_legend",
        "📖 Изучение легенды",
        "Изучение легенды"
    ),
    (
        "stage_fake_resume",
        "💼 Поиск работы на тренировочном резюме",
        "Поиск работы на фейк резюме"
    ),
    (
        "stage_real_resume",
        "💼 Поиск работы на реальном резюме",
        "Поиск работы на реальном резюме"
    )
]

def register_student_handlers(dp: Dispatcher, db: Database, notification_service: NotificationService):
    
    # Создаем клавиатуру для учеников
    student_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Отправить отчет"), KeyboardButton(text="📊 Мои отчеты")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    @dp.message(Command("start"))
    async def start_handler(message: Message):
        user = message.from_user
        await db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Используем адаптивную систему помощи
        from bot import get_role_based_help
        help_text, keyboard = await get_role_based_help(user.id)
        
        # Добавляем приветственное сообщение
        greeting = "Привет! Я бот для сбора еженедельных отчетов.\n\n"
        await message.answer(greeting + help_text, reply_markup=keyboard)

    @dp.message(Command("help"))
    async def help_handler(message: Message):
        from bot import get_role_based_help
        help_text, keyboard = await get_role_based_help(message.from_user.id)
        await message.answer(help_text, reply_markup=keyboard)

    # Обработчики кнопок
    @dp.message(lambda message: message.text == "📝 Отправить отчет")
    async def button_report_handler(message: Message, state: FSMContext):
        await report_handler(message, state)

    @dp.message(lambda message: message.text == "📊 Мои отчеты")
    async def button_my_reports_handler(message: Message):
        await my_reports_handler(message)

    @dp.message(lambda message: message.text == "❓ Помощь")
    async def button_help_handler(message: Message):
        await help_handler(message)

    @dp.message(Command("report"))
    async def report_handler(message: Message, state: FSMContext):
        user_id = message.from_user.id
        
        # Проверяем, есть ли у ученика закрепленный куратор
        curator = await db.get_student_curator(user_id)
        if not curator:
            await message.answer(
                "❌ *У тебя нет закрепленного куратора!*\n\n"
                "Для отправки отчетов необходимо, чтобы за тобой был закреплен куратор.\n\n"
                "*Пожалуйста, напишите об этом в группу менторства*.\n\n"
                "После назначения куратора ты сможешь отправлять отчеты.",
                reply_markup=student_keyboard,
                parse_mode='Markdown'
            )
            return
        
        # Проверяем, есть ли уже отчет за текущую неделю
        current_week_reports = await db.get_reports_for_current_week(user_id)
        if current_week_reports:
            from datetime import datetime
            report_date = datetime.fromisoformat(current_week_reports[0]['created_at'])
            await message.answer(
                f"⏰ *Отчет за эту неделю уже отправлен!*\n\n"
                f"Твой отчет за текущую неделю был отправлен {report_date.strftime('%d.%m.%Y в %H:%M')}\n"
                f"Следующий отчет можно будет отправить в понедельник.\n\n"
                f"Используй кнопку '📊 Мои отчеты' для просмотра всех отчетов.",
                reply_markup=student_keyboard,
                parse_mode='Markdown'
            )
            return
        
        # Получаем последний выбранный этап для предустановки
        last_stage = await db.get_last_stage_choice(user_id)
        
        # Создаем клавиатуру с предустановленными блоками
        stage_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=label, callback_data=callback)]
                for callback, label, _ in STAGE_OPTIONS
            ]
        )
        
        await state.set_state(ReportStates.waiting_for_stage_selection)
        
        message_text = "📝 Начинаем заполнение еженедельного отчета!\n\n*Выбери свой текущий этап:*"
        
        if last_stage:
            last_stage_display = escape_markdown(last_stage)
            message_text += f"\n\n💡 *Рекомендация:* В прошлый раз ты выбрал `{last_stage_display}`"
        
        await message.answer(message_text, reply_markup=stage_keyboard, parse_mode='Markdown')

    @dp.message(Command("my_reports"))
    async def my_reports_handler(message: Message):
        user_id = message.from_user.id
        reports = await db.get_user_reports(user_id)
        
        if not reports:
            await message.answer("У тебя пока нет отчетов.")
            return
        
        # Проверяем, есть ли отчет за текущую неделю
        current_week_reports = await db.get_reports_for_current_week(user_id)
        next_report_info = ""
        if current_week_reports:
            report_date = datetime.fromisoformat(current_week_reports[0]['created_at'])
            next_report_info = f"\n⏰ Отчет за эту неделю уже отправлен ({report_date.strftime('%d.%m.%Y')})\n📅 Следующий отчет можно отправить в понедельник"
        else:
            next_report_info = "\n✅ Можно отправить отчет за эту неделю!"
        
        response = "📊 Твои отчеты:\n\n"
        for i, report in enumerate(reports[:5], 1):
            date = datetime.fromisoformat(report['created_at']).strftime('%d.%m.%Y')
            stage = escape_markdown(report['current_stage'])
            plans_preview_raw = report['plans'][:50]
            plans_preview = escape_markdown(plans_preview_raw)
            plans_suffix = '...' if len(report['plans']) > 50 else ''
            
            response += f"*{i}. {date}*\n"
            response += f"🎯 Этап: {stage}\n"
            response += f"📋 Планы: {plans_preview}{plans_suffix}\n"
            
            if report['plans_completed'] is not None:
                if report['plans_completed']:
                    response += f"✅ Выполнение планов: Да\n"
                else:
                    response += f"❌ Выполнение планов: Нет\n"
                    if report['plans_failure_reason']:
                        reason_preview_raw = report['plans_failure_reason'][:50]
                        reason_preview = escape_markdown(reason_preview_raw)
                        reason_suffix = '...' if len(report['plans_failure_reason']) > 50 else ''
                        response += f"📝 Причина: {reason_preview}{reason_suffix}\n"
            
            problems_preview_raw = report['problems'][:50]
            problems_preview = escape_markdown(problems_preview_raw)
            problems_suffix = '...' if len(report['problems']) > 50 else ''
            response += f"❓ Проблемы: {problems_preview}{problems_suffix}\n\n"
        
        if len(reports) > 5:
            response += f"... и еще {len(reports) - 5} отчетов"
        
        response += next_report_info
        
        await message.answer(response, parse_mode='Markdown')

    # Обработчик выбора этапа
    @dp.callback_query(lambda c: c.data.startswith('stage_'))
    async def process_stage_selection(callback, state: FSMContext):
        stage_mapping = {callback: value for callback, _, value in STAGE_OPTIONS}
        
        selected_stage = stage_mapping.get(callback.data)
        if selected_stage:
            await state.update_data(current_stage=selected_stage)
            await state.set_state(ReportStates.waiting_for_plans)
            
            cancel_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            has_previous = await db.has_previous_reports(callback.from_user.id)
            selected_stage_display = escape_markdown(selected_stage)
            
            if has_previous:
                await state.set_state(ReportStates.waiting_for_plans_completion)
                completion_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Да, выполнил", callback_data="plans_yes")],
                        [InlineKeyboardButton(text="❌ Нет, не выполнил", callback_data="plans_no")]
                    ]
                )
                
                await callback.message.edit_text(
                    f"✅ *Выбран этап:* {selected_stage_display}\n\n"
                    "*Удалось ли выполнить все запланированное на этой неделе?*",
                    parse_mode='Markdown'
                )
                await callback.message.answer(
                    "Пожалуйста, выбери ответ:",
                    reply_markup=completion_keyboard
                )
            else:
                await callback.message.edit_text(
                    f"✅ *Выбран этап:* {selected_stage_display}\n\n"
                    "*Что планируешь делать на следующую неделю?*\n\n"
                    "Опиши свои планы:",
                    parse_mode='Markdown'
                )
                await callback.message.answer(
                    "Пожалуйста, опиши свои планы:",
                    reply_markup=cancel_keyboard
                )
            
            await callback.answer()

    @dp.message(ReportStates.waiting_for_stage_selection)
    async def process_stage_selection_text(message: Message, state: FSMContext):
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("❌ Заполнение отчета отменено.", reply_markup=student_keyboard)
            return
        
        # Если пользователь написал текст вместо выбора кнопки, показываем подсказку
        await message.answer(
            "Пожалуйста, выбери этап из предложенных кнопок выше ⬆️",
            reply_markup=student_keyboard
        )

    # Обработчик выбора выполнения планов
    @dp.callback_query(lambda c: c.data in ['plans_yes', 'plans_no'])
    async def process_plans_completion(callback, state: FSMContext):
        if callback.data == 'plans_yes':
            await state.update_data(plans_completed=True)
            await state.set_state(ReportStates.waiting_for_plans)
            
            cancel_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await callback.message.edit_text(
                "✅ *Отлично!* ты выполнили все запланированное.\n\n"
                "*Что планируешь делать на следующую неделю?*",
                parse_mode='Markdown'
            )
            await callback.message.answer(
                "Пожалуйста, опиши свои планы:",
                reply_markup=cancel_keyboard
            )
        else:  # plans_no
            await state.update_data(plans_completed=False)
            await state.set_state(ReportStates.waiting_for_plans_failure_reason)
            
            cancel_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await callback.message.edit_text(
                "❌ *Понятно.* Не все запланированное удалось выполнить.\n\n"
                "*Почему не удалось выполнить планы?*",
                parse_mode='Markdown'
            )
            await callback.message.answer(
                "Пожалуйста, объясни причины:",
                reply_markup=cancel_keyboard
            )
        
        await callback.answer()

    @dp.message(ReportStates.waiting_for_plans_completion)
    async def process_plans_completion_text(message: Message, state: FSMContext):
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("❌ Заполнение отчета отменено.", reply_markup=student_keyboard)
            return
        
        await message.answer(
            "Пожалуйста, выберите ответ из предложенных кнопок выше ⬆️",
            reply_markup=student_keyboard
        )

    @dp.message(ReportStates.waiting_for_plans_failure_reason)
    async def process_plans_failure_reason(message: Message, state: FSMContext):
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("❌ Заполнение отчета отменено.", reply_markup=student_keyboard)
            return
            
        if len(message.text) < 5:
            await message.answer("Пожалуйста, напишите более подробно о причинах (минимум 5 символов).")
            return
        
        await state.update_data(plans_failure_reason=message.text)
        await state.set_state(ReportStates.waiting_for_plans)
        
        cancel_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "*Что планируешь делать на следующую неделю?*\n\n"
            "Опиши свои планы:",
            reply_markup=cancel_keyboard,
            parse_mode='Markdown'
        )

    @dp.message(ReportStates.waiting_for_plans)
    async def process_plans(message: Message, state: FSMContext):
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("❌ Заполнение отчета отменено.", reply_markup=student_keyboard)
            return
            
        if len(message.text) < 5:
            await message.answer("Пожалуйста, напиши более подробно о своих планах (минимум 5 символов).")
            return
        
        await state.update_data(plans=message.text)
        await state.set_state(ReportStates.waiting_for_problems)
        
        cancel_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "*Есть ли проблемы или вопросы?*\n\n"
            "Опишите трудности, с которыми столкнулись, или вопросы, которые у тебя есть.",
            reply_markup=cancel_keyboard,
            parse_mode='Markdown'
        )

    @dp.message(ReportStates.waiting_for_problems)
    async def process_problems(message: Message, state: FSMContext):
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("❌ Заполнение отчета отменено.", reply_markup=student_keyboard)
            return
            
        data = await state.get_data()
        user_id = message.from_user.id
        
        await db.save_report(
            user_id=user_id,
            current_stage=data['current_stage'],
            plans=data['plans'],
            problems=message.text,
            plans_completed=data.get('plans_completed'),
            plans_failure_reason=data.get('plans_failure_reason')
        )
        
        await state.clear()
        current_stage_display = escape_markdown(data['current_stage'])
        plans_display = escape_markdown(data['plans'])
        problems_display = escape_markdown(message.text)
        await message.answer(
            "✅ *Отчет сохранен!*\n\n"
            f"🎯 *Этап:* {current_stage_display}\n"
            f"📋 *Планы:* {plans_display}\n"
            f"❓ *Проблемы:* {problems_display}\n\n"
            "Спасибо за твою работу! Следующее напоминание придет через неделю.",
            reply_markup=student_keyboard,
            parse_mode='Markdown'
        )
        
        # Уведомляем куратора о новом отчете
        await notification_service.notify_curator_new_report(user_id, {
            'current_stage': data['current_stage'],
            'plans': data['plans'],
            'problems': message.text
        })
