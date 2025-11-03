import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace
from datetime import datetime

from handlers.curator_handlers import register_curator_handlers
from tests.utils import (
    FakeDispatcher,
    FakeFSMContext,
    FakeMessage,
    FakeCallbackQuery,
    FakeCallbackMessage,
)


@pytest.fixture
def setup_curator_handlers():
    dispatcher = FakeDispatcher()
    db = AsyncMock()
    db.is_admin = AsyncMock()
    db.get_user_type = AsyncMock()
    db.add_user = AsyncMock()
    db.add_curator_student_relation = AsyncMock()
    db.get_curator_students = AsyncMock()
    db.get_all_students_with_curators = AsyncMock()
    db.get_unread_reports_for_curator = AsyncMock()
    db.mark_report_as_read = AsyncMock()
    db.get_report_by_id = AsyncMock()

    notification_service = SimpleNamespace(
        notify_student_curator_assigned=AsyncMock(),
        notify_student_report_read=AsyncMock(),
    )

    register_curator_handlers(dispatcher, db, notification_service)
    return dispatcher, db, notification_service


@pytest.mark.asyncio
async def test_curator_handler_denies_access(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["curator_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = False
    db.get_user_type.return_value = "student"

    await handler(message)

    db.add_user.assert_not_awaited()
    assert len(message.answers) == 1
    assert "доступ запрещен" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_curator_handler_allows_admin_activation(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["curator_handler"]
    message = FakeMessage(user_id=42, username="curator", first_name="Ivan", last_name="Ivanov")
    db.is_admin.return_value = True
    db.get_user_type.return_value = "student"

    await handler(message)

    db.add_user.assert_awaited_once_with(
        user_id=42,
        username="curator",
        first_name="Ivan",
        last_name="Ivanov",
        user_type="curator",
    )
    assert len(message.answers) == 1
    assert "режим куратора активирован" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_student_id_validates_integer(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["process_student_id"]
    message = FakeMessage(user_id=5, text="abc")
    state = FakeFSMContext()

    await handler(message, state)

    db.add_curator_student_relation.assert_not_awaited()
    assert state.cleared is False
    assert len(message.answers) == 1
    assert "корректный id" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_student_id_adds_student_and_notifies(setup_curator_handlers):
    dispatcher, db, notification_service = setup_curator_handlers
    handler = dispatcher.message_handlers["process_student_id"]
    message = FakeMessage(user_id=10, text="123")
    state = FakeFSMContext()

    await handler(message, state)

    db.add_curator_student_relation.assert_awaited_once_with(10, 123)
    assert state.cleared is True
    assert len(message.answers) == 1
    assert "ученик с id" in message.answers[0][0].lower()
    notification_service.notify_student_curator_assigned.assert_awaited_once_with(123)


@pytest.mark.asyncio
async def test_reports_handler_displays_unread_reports(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["reports_handler"]
    message = FakeMessage(user_id=7)
    db.get_unread_reports_for_curator.return_value = [
        {
            "id": 1,
            "user_id": 20,
            "student_name": "Student One",
            "current_stage": "stage",
            "plans": "plans",
            "problems": "problems",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    ]

    await handler(message)

    db.get_unread_reports_for_curator.assert_awaited_once_with(7)
    assert len(message.answers) == 1
    text, kwargs = message.answers[0]
    assert "отчет от" in text.lower()
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_mark_report_read_marks_and_notifies(setup_curator_handlers):
    dispatcher, db, notification_service = setup_curator_handlers
    handler = dispatcher.callback_handlers["mark_report_read"]
    callback_message = FakeCallbackMessage(text="Report text")
    callback = FakeCallbackQuery(user_id=7, data="read_3", message=callback_message)
    db.get_report_by_id.return_value = {
        "user_id": 20,
        "current_stage": "stage",
        "plans": "plans",
        "problems": "problems",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    await handler(callback)

    db.mark_report_as_read.assert_awaited_once_with(3, 7)
    db.get_report_by_id.assert_awaited_once_with(3)
    notification_service.notify_student_report_read.assert_awaited_once_with(
        20,
        db.get_report_by_id.return_value,
    )
    assert callback.answers and "отчет отмечен" in callback.answers[0][0].lower()
    assert callback_message.edits and "прочитано" in callback_message.edits[0][0].lower()


@pytest.mark.asyncio
async def test_my_students_handler_shows_empty_list(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["my_students_handler"]
    message = FakeMessage(user_id=10)
    db.get_curator_students.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "пока нет учеников" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_my_students_handler_shows_students_list(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["my_students_handler"]
    message = FakeMessage(user_id=10)
    db.get_curator_students.return_value = [
        {"user_id": 1, "first_name": "Stu", "last_name": "Dent", "username": "student1"},
        {"user_id": 2, "first_name": None, "last_name": None, "username": "student2"}
    ]

    await handler(message)

    assert len(message.answers) == 1
    assert "твои ученики" in message.answers[0][0].lower()
    assert "Stu Dent" in message.answers[0][0]
    assert "student2" in message.answers[0][0]


@pytest.mark.asyncio
async def test_reports_handler_shows_more_than_5_reports_message(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["reports_handler"]
    message = FakeMessage(user_id=7)
    reports = [
        {
            "id": i,
            "user_id": 20,
            "student_name": f"Student {i}",
            "current_stage": "stage",
            "plans": "plans",
            "problems": "problems",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        for i in range(1, 8)
    ]
    db.get_unread_reports_for_curator.return_value = reports

    await handler(message)

    assert len(message.answers) == 6
    assert "и еще 2 отчетов" in message.answers[-1][0]


@pytest.mark.asyncio
async def test_reports_handler_shows_no_reports(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["reports_handler"]
    message = FakeMessage(user_id=7)
    db.get_unread_reports_for_curator.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "нет непрочитанных отчетов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_all_students_handler_shows_all_students(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["all_students_handler"]
    message = FakeMessage(user_id=7)
    db.get_all_students_with_curators.return_value = [
        {
            "user_id": 1,
            "first_name": "Stu",
            "last_name": "Dent",
            "username": "student",
            "curator_id": 10,
            "curator_first_name": "Cur",
            "curator_last_name": "Ator",
            "curator_username": "curator"
        },
        {
            "user_id": 2,
            "first_name": "Other",
            "last_name": "Student",
            "username": "other",
            "curator_id": None,
            "curator_first_name": None,
            "curator_last_name": None,
            "curator_username": None
        }
    ]

    await handler(message)

    assert len(message.answers) == 1
    assert "все ученики и их кураторы" in message.answers[0][0].lower()
    assert "Stu Dent" in message.answers[0][0]
    assert "Без куратора" in message.answers[0][0]


@pytest.mark.asyncio
async def test_all_students_handler_empty_list(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["all_students_handler"]
    message = FakeMessage(user_id=7)
    db.get_all_students_with_curators.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "пока нет учеников" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_curator_handler_updates_user_info(setup_curator_handlers):
    dispatcher, db, _ = setup_curator_handlers
    handler = dispatcher.message_handlers["curator_handler"]
    message = FakeMessage(user_id=42, username="curator", first_name="Ivan", last_name="Ivanov")
    db.is_admin.return_value = False
    db.get_user_type.return_value = "curator"

    await handler(message)

    db.add_user.assert_awaited_once_with(
        user_id=42,
        username="curator",
        first_name="Ivan",
        last_name="Ivanov",
        user_type="curator",
    )
    assert "режим куратора активирован" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_mark_report_read_without_report_found(setup_curator_handlers):
    dispatcher, db, notification_service = setup_curator_handlers
    handler = dispatcher.callback_handlers["mark_report_read"]
    callback_message = FakeCallbackMessage(text="Report text")
    callback = FakeCallbackQuery(user_id=7, data="read_3", message=callback_message)
    db.get_report_by_id.return_value = None

    await handler(callback)

    db.mark_report_as_read.assert_awaited_once_with(3, 7)
    notification_service.notify_student_report_read.assert_not_awaited()

