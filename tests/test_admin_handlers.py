import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace

from handlers.admin_handlers import register_admin_handlers
from tests.utils import FakeDispatcher, FakeFSMContext, FakeMessage
from states import AdminStates


@pytest.fixture
def setup_admin_handlers():
    dispatcher = FakeDispatcher()
    db = AsyncMock()
    db.is_admin = AsyncMock()
    db.get_all_curators = AsyncMock()
    db.get_curator_stats = AsyncMock()
    db.get_students_without_curators = AsyncMock()
    db.get_all_students_with_curators = AsyncMock()
    db.add_user = AsyncMock()
    db.assign_student_to_curator = AsyncMock()
    db.deactivate_curator = AsyncMock()
    db.activate_curator = AsyncMock()
    db.get_student_curator = AsyncMock()
    db.remove_curator_student_relation = AsyncMock()

    notification_service = SimpleNamespace(
        notify_student_curator_assigned=AsyncMock(),
        send_curator_missing_reports_notifications=AsyncMock(),
    )

    register_admin_handlers(dispatcher, db, notification_service)
    return dispatcher, db, notification_service


@pytest.mark.asyncio
async def test_admin_handler_denied_without_access(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["admin_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = False

    await handler(message)

    assert len(message.answers) == 1
    assert "нет прав администратора" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_admin_handler_shows_menu_for_admin(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["admin_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True

    await handler(message)

    assert len(message.answers) == 1
    assert "панель администратора" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_all_curators_handler_lists_curators(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["all_curators_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True
    db.get_all_curators.return_value = [
        {
            "user_id": 10,
            "username": "curator",
            "first_name": "Cur",
            "last_name": "Ator",
        }
    ]
    db.get_curator_stats.return_value = {
        "student_count": 2,
        "total_reports": 5,
        "unread_reports": 1,
    }

    await handler(message)

    db.get_curator_stats.assert_awaited_once_with(10)
    assert len(message.answers) == 1
    assert "все кураторы" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_admin_stats_handler_combines_data(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["admin_stats_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True
    db.get_all_curators.return_value = [
        {"user_id": 10, "first_name": "Cur", "last_name": "Ator", "username": "curator"}
    ]
    db.get_all_students_with_curators.return_value = [
        {"user_id": 1, "curator_id": 10}
    ]
    db.get_students_without_curators.return_value = [
        {"user_id": 2}
    ]
    db.get_curator_stats.return_value = {
        "student_count": 1,
        "total_reports": 3,
        "unread_reports": 0,
    }

    await handler(message)

    assert len(message.answers) == 1
    text = message.answers[0][0]
    assert "общая статистика системы" in text.lower()
    assert "всего кураторов" in text.lower()


@pytest.mark.asyncio
async def test_add_curator_handler_sets_state(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["add_curator_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.is_admin.return_value = True

    await handler(message, state)

    assert state.state == AdminStates.waiting_for_curator_id
    data = await state.get_data()
    assert data["curator_action"] == "add"
    assert "добавление куратора" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_curator_id_assigns_on_add(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_curator_id"]
    message = FakeMessage(user_id=1, text="55")
    state = FakeFSMContext()
    await state.update_data(curator_action="add")

    await handler(message, state)

    db.add_user.assert_awaited_once_with(user_id=55, user_type="curator")
    assert state.cleared is True
    assert "назначен куратором" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_assign_student_handler_prepares_lists(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["assign_student_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.is_admin.return_value = True
    db.get_students_without_curators.return_value = [
        {"user_id": 1, "first_name": "Stu", "last_name": "Dent", "username": "student"}
    ]
    db.get_all_curators.return_value = [
        {"user_id": 10, "first_name": "Cur", "last_name": "Ator", "username": "curator"}
    ]

    await handler(message, state)

    assert state.state == AdminStates.waiting_for_student_to_assign
    data = await state.get_data()
    assert data["students"][0]["user_id"] == 1
    assert data["curators"][0]["user_id"] == 10
    assert "выбери ученика" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_student_selection_moves_to_curator_choice(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_student_selection"]
    message = FakeMessage(user_id=1, text="1")
    state = FakeFSMContext()
    await state.update_data(
        students=[{"user_id": 2, "first_name": "Stu", "last_name": "Dent"}],
        curators=[{"user_id": 10, "first_name": "Cur", "last_name": "Ator"}],
    )

    await handler(message, state)

    assert state.state == AdminStates.waiting_for_curator_to_assign
    data = await state.get_data()
    assert data["selected_student"]["user_id"] == 2
    assert "выбран ученик" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_curator_selection_assigns_student(setup_admin_handlers):
    dispatcher, db, notification_service = setup_admin_handlers
    handler = dispatcher.message_handlers["process_curator_selection"]
    message = FakeMessage(user_id=1, text="1")
    state = FakeFSMContext()
    await state.update_data(
        curators=[{"user_id": 10, "first_name": "Cur", "last_name": "Ator"}],
        selected_student={"user_id": 2, "first_name": "Stu", "last_name": "Dent"},
    )

    await handler(message, state)

    db.assign_student_to_curator.assert_awaited_once_with(2, 10)
    assert state.cleared is True
    assert "назначение выполнено" in message.answers[0][0].lower()
    notification_service.notify_student_curator_assigned.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_process_curator_id_deactivates(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_curator_id"]
    message = FakeMessage(user_id=1, text="77")
    state = FakeFSMContext()
    await state.update_data(curator_action="deactivate")

    await handler(message, state)

    db.deactivate_curator.assert_awaited_once_with(77)
    assert state.cleared is True
    assert "деактивирован" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_curator_id_activates(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_curator_id"]
    message = FakeMessage(user_id=1, text="88")
    state = FakeFSMContext()
    await state.update_data(curator_action="activate")

    await handler(message, state)

    db.activate_curator.assert_awaited_once_with(88)
    assert state.cleared is True
    assert "активирован" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_remove_relation_removes_when_curator_exists(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_remove_relation"]
    message = FakeMessage(user_id=1, text="5")
    state = FakeFSMContext()
    db.get_student_curator.return_value = {"user_id": 10, "first_name": "Cur", "last_name": "Ator"}

    await handler(message, state)

    db.remove_curator_student_relation.assert_awaited_once_with(10, 5)
    assert state.cleared is True
    assert "связь с куратором удалена" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_remove_relation_handles_missing_curator(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_remove_relation"]
    message = FakeMessage(user_id=1, text="5")
    state = FakeFSMContext()
    db.get_student_curator.return_value = None

    await handler(message, state)

    db.remove_curator_student_relation.assert_not_awaited()
    assert state.cleared is False
    assert "нет куратора" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_student_selection_invalid_number_out_of_range(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_student_selection"]
    message = FakeMessage(user_id=1, text="999")
    state = FakeFSMContext()
    await state.update_data(
        students=[{"user_id": 2, "first_name": "Stu", "last_name": "Dent"}],
        curators=[{"user_id": 10, "first_name": "Cur", "last_name": "Ator"}],
    )

    await handler(message, state)

    assert "неверный номер" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_curator_selection_invalid_number_out_of_range(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_curator_selection"]
    message = FakeMessage(user_id=1, text="999")
    state = FakeFSMContext()
    await state.update_data(
        curators=[{"user_id": 10, "first_name": "Cur", "last_name": "Ator"}],
        selected_student={"user_id": 2, "first_name": "Stu", "last_name": "Dent"},
    )

    await handler(message, state)

    assert "неверный номер" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_all_students_admin_handler_shows_all_students(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["all_students_admin_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True
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
        }
    ]

    await handler(message)

    assert len(message.answers) == 1
    assert "все ученики в системе" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_all_students_admin_handler_shows_empty_list(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["all_students_admin_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True
    db.get_all_students_with_curators.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "нет учеников" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_notify_curators_handler_sends_notifications(setup_admin_handlers):
    dispatcher, db, notification_service = setup_admin_handlers
    handler = dispatcher.message_handlers["notify_curators_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True

    await handler(message)

    notification_service.send_curator_missing_reports_notifications.assert_awaited_once()
    assert len(message.answers) == 1
    assert "уведомления" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_students_without_curators_handler_shows_students(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["students_without_curators_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True
    db.get_students_without_curators.return_value = [
        {"user_id": 1, "first_name": "Stu", "last_name": "Dent", "username": "student"}
    ]

    await handler(message)

    assert len(message.answers) == 1
    assert "без кураторов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_students_without_curators_handler_shows_all_assigned(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["students_without_curators_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True
    db.get_students_without_curators.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "все ученики имеют кураторов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_assign_student_handler_no_curators(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["assign_student_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.is_admin.return_value = True
    db.get_students_without_curators.return_value = [{"user_id": 1}]
    db.get_all_curators.return_value = []

    await handler(message, state)

    assert len(message.answers) == 1
    assert "нет кураторов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_assign_student_handler_all_assigned(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["assign_student_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.is_admin.return_value = True
    db.get_students_without_curators.return_value = []
    db.get_all_curators.return_value = [{"user_id": 10}]

    await handler(message, state)

    assert len(message.answers) == 1
    assert "все ученики уже имеют кураторов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_all_curators_handler_empty_list(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["all_curators_handler"]
    message = FakeMessage(user_id=1)
    db.is_admin.return_value = True
    db.get_all_curators.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "нет кураторов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_curator_id_invalid_format(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_curator_id"]
    message = FakeMessage(user_id=1, text="abc")
    state = FakeFSMContext()
    await state.update_data(curator_action="add")

    await handler(message, state)

    db.add_user.assert_not_awaited()
    assert "корректный id" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_remove_relation_invalid_id(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_remove_relation"]
    message = FakeMessage(user_id=1, text="abc")
    state = FakeFSMContext()

    await handler(message, state)

    db.get_student_curator.assert_not_awaited()
    assert "корректный id" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_student_selection_empty_list(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_student_selection"]
    message = FakeMessage(user_id=1, text="1")
    state = FakeFSMContext()
    await state.update_data(students=[], curators=[])

    await handler(message, state)

    assert state.cleared is True
    assert "недоступен" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_curator_selection_empty_list(setup_admin_handlers):
    dispatcher, db, _ = setup_admin_handlers
    handler = dispatcher.message_handlers["process_curator_selection"]
    message = FakeMessage(user_id=1, text="1")
    state = FakeFSMContext()
    await state.update_data(curators=[], selected_student=None)

    await handler(message, state)

    assert state.cleared is True
    assert "недоступны" in message.answers[0][0].lower()

