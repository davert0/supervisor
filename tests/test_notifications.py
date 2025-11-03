import pytest
from unittest.mock import AsyncMock

import text_utils
from notifications import NotificationService


@pytest.fixture
def bot_mock():
    return AsyncMock()


@pytest.fixture
def db_mock():
    mock = AsyncMock()
    return mock


@pytest.fixture
def notification_service(bot_mock, db_mock):
    return NotificationService(bot_mock, db_mock)


def test_format_user_name_prefers_full_name(notification_service):
    result = notification_service._format_user_name(
        {"first_name": "Ivan", "last_name": "Ivanov", "username": "ivan"},
        1,
    )

    assert result == "Ivan Ivanov"


def test_format_user_name_falls_back_to_username(notification_service):
    result = notification_service._format_user_name(
        {"username": "ivan"},
        1,
    )

    assert result == "ivan"


def test_format_user_name_uses_fallback(notification_service):
    result = notification_service._format_user_name(None, 5)

    assert result == "ID: 5"


@pytest.mark.asyncio
async def test_notify_curator_new_report_sends_message(notification_service, bot_mock, db_mock):
    db_mock.get_student_curator.return_value = {"user_id": 100}
    db_mock.get_user_profile.return_value = {
        "first_name": "Ivan",
        "last_name": "Ivanov",
        "username": "ivan",
    }

    report = {"current_stage": "Stage", "plans": "Plan", "problems": "Problem"}

    await notification_service.notify_curator_new_report(1, report)

    bot_mock.send_message.assert_awaited_once_with(
        100,
        "📝 *Новый отчет от Ivan Ivanov!*\n\n"
        "🎯 *Этап:* Stage\n"
        "📋 *Планы:* Plan\n"
        "❓ *Проблемы:* Problem\n\n"
        "Используйте `/reports` для просмотра всех отчетов.",
    )


@pytest.mark.asyncio
async def test_notify_curator_new_report_skips_without_curator(notification_service, bot_mock, db_mock):
    db_mock.get_student_curator.return_value = None

    await notification_service.notify_curator_new_report(1, {"current_stage": "Stage", "plans": "Plan", "problems": "Problem"})

    bot_mock.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_weekly_reminders_only_notifies_missing(notification_service, bot_mock, db_mock):
    db_mock.get_all_active_users.return_value = [
        {"user_id": 1},
        {"user_id": 2},
    ]
    db_mock.get_reports_for_current_week.side_effect = [[{"dummy": 1}], []]

    await notification_service.send_weekly_reminders()

    bot_mock.send_message.assert_awaited_once_with(
        2,
        text_utils.escape_markdown(
            "📝 *Время для еженедельного отчета!*\n\n"
            "Пожалуйста, заполни отчет по форме:\n"
            "• На каком сейчас этапе? (этап + тема)\n"
            "• Что планируешь делать?\n"
            "• Есть ли проблемы или вопросы?\n\n"
            "Используй кнопку '📝 Отправить отчет' для начала заполнения."
        ),
    )


@pytest.mark.asyncio
async def test_send_curator_missing_reports_notifications_groups_students(notification_service, bot_mock, db_mock):
    db_mock.get_students_missing_weekly_reports.return_value = [
        {
            "curator_id": 100,
            "curator_username": "curator",
            "curator_first_name": "Cur",
            "curator_last_name": "Ator",
            "student_id": 1,
            "student_username": "student1",
            "student_first_name": "Stu",
            "student_last_name": "Dent",
        },
        {
            "curator_id": 100,
            "curator_username": "curator",
            "curator_first_name": "Cur",
            "curator_last_name": "Ator",
            "student_id": 2,
            "student_username": "student2",
            "student_first_name": None,
            "student_last_name": None,
        },
    ]

    await notification_service.send_curator_missing_reports_notifications()

    bot_mock.send_message.assert_awaited_once_with(
        100,
        "⚠️ *Уведомление куратора*\n\n"
        "Следующие ученики не отправили отчет за эту неделю:\n\n"
        "• Stu Dent\n"
        "• student2\n\n"
        "Рекомендуется связаться с ними для выяснения причин.",
    )


@pytest.mark.asyncio
async def test_send_curator_missing_reports_notifications_skips_when_empty(notification_service, bot_mock, db_mock):
    db_mock.get_students_missing_weekly_reports.return_value = []

    await notification_service.send_curator_missing_reports_notifications()

    bot_mock.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_curator_new_report_handles_bot_exception(notification_service, bot_mock, db_mock):
    db_mock.get_student_curator.return_value = {"user_id": 100}
    db_mock.get_user_profile.return_value = {"first_name": "Ivan", "last_name": "Ivanov"}
    bot_mock.send_message.side_effect = Exception("Bot blocked")
    
    await notification_service.notify_curator_new_report(1, {"current_stage": "Stage", "plans": "Plan", "problems": "Problem"})
    
    bot_mock.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_student_curator_assigned_sends_correct_message(notification_service, bot_mock):
    await notification_service.notify_student_curator_assigned(123)
    
    bot_mock.send_message.assert_awaited_once()
    args = bot_mock.send_message.await_args
    assert args[0][0] == 123
    assert "К тебе назначен куратор" in args[0][1]


@pytest.mark.asyncio
async def test_notify_student_curator_assigned_handles_exception(notification_service, bot_mock):
    bot_mock.send_message.side_effect = Exception("Network error")
    
    await notification_service.notify_student_curator_assigned(123)
    
    bot_mock.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_student_report_read_sends_correct_message(notification_service, bot_mock):
    report_data = {
        "current_stage": "Stage 1",
        "plans": "Some plans",
        "problems": "Some problems"
    }
    
    await notification_service.notify_student_report_read(456, report_data)
    
    bot_mock.send_message.assert_awaited_once()
    args = bot_mock.send_message.await_args
    assert args[0][0] == 456
    assert "просмотрен куратором" in args[0][1]
    assert "Stage 1" in args[0][1]


@pytest.mark.asyncio
async def test_notify_student_report_read_handles_exception(notification_service, bot_mock):
    bot_mock.send_message.side_effect = Exception("User blocked bot")
    report_data = {
        "current_stage": "Stage 1",
        "plans": "Plans",
        "problems": "Problems"
    }
    
    await notification_service.notify_student_report_read(456, report_data)
    
    bot_mock.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_weekly_reminders_handles_exception_for_individual_user(notification_service, bot_mock, db_mock):
    db_mock.get_all_active_users.return_value = [
        {"user_id": 1},
        {"user_id": 2},
    ]
    db_mock.get_reports_for_current_week.return_value = []
    bot_mock.send_message.side_effect = [Exception("First user blocked"), None]
    
    await notification_service.send_weekly_reminders()
    
    assert bot_mock.send_message.await_count == 2


@pytest.mark.asyncio
async def test_send_curator_missing_reports_notifications_handles_exception(notification_service, bot_mock, db_mock):
    db_mock.get_students_missing_weekly_reports.return_value = [
        {
            "curator_id": 100,
            "curator_username": "curator",
            "curator_first_name": "Cur",
            "curator_last_name": "Ator",
            "student_id": 1,
            "student_username": "student1",
            "student_first_name": "Stu",
            "student_last_name": "Dent",
        }
    ]
    bot_mock.send_message.side_effect = Exception("Curator blocked bot")

    await notification_service.send_curator_missing_reports_notifications()

    bot_mock.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_format_user_name_handles_only_first_name(notification_service):
    result = notification_service._format_user_name(
        {"first_name": "Ivan", "last_name": None, "username": "ivan"},
        1,
    )

    assert result == "ivan"


@pytest.mark.asyncio
async def test_format_user_name_handles_only_last_name(notification_service):
    result = notification_service._format_user_name(
        {"first_name": None, "last_name": "Ivanov", "username": "ivan"},
        1,
    )

    assert result == "ivan"


@pytest.mark.asyncio
async def test_send_weekly_reminders_retries_transient_error(notification_service, bot_mock, db_mock, monkeypatch):
    db_mock.get_all_active_users.return_value = [
        {"user_id": 1},
    ]
    db_mock.get_reports_for_current_week.return_value = []
    bot_mock.send_message.side_effect = [Exception("Timeout"), None]
    monkeypatch.setattr("notifications.asyncio.sleep", AsyncMock())

    await notification_service.send_weekly_reminders()

    assert bot_mock.send_message.await_count == 2


@pytest.mark.asyncio
async def test_send_daily_missing_report_reminders_only_notifies_missing(notification_service, bot_mock, db_mock):
    db_mock.get_all_active_users.return_value = [
        {"user_id": 1},
        {"user_id": 2},
    ]
    db_mock.get_reports_for_current_week.side_effect = [[], [{"dummy": 1}]]

    await notification_service.send_daily_missing_report_reminders()

    bot_mock.send_message.assert_awaited_once_with(
        1,
        text_utils.escape_markdown(
            "🔔 *Напоминание об отчете!*\n\n"
            "Мы ждем твой еженедельный отчет. Заполни форму, чтобы поделиться прогрессом."
        ),
    )

