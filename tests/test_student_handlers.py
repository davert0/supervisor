from datetime import datetime
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from handlers.student_handlers import register_student_handlers
from states import ReportStates
from tests.utils import FakeDispatcher, FakeFSMContext, FakeMessage


@pytest.fixture
def setup_handlers():
    dispatcher = FakeDispatcher()
    db = AsyncMock()
    notification_service = SimpleNamespace(notify_curator_new_report=AsyncMock())
    register_student_handlers(dispatcher, db, notification_service)
    return dispatcher, db, notification_service


@pytest.mark.asyncio
async def test_report_handler_without_curator(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["report_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.get_student_curator.return_value = None

    await handler(message, state)

    assert db.get_student_curator.await_args[0][0] == 1
    assert len(message.answers) == 1
    assert "нет закрепленного куратора" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_report_handler_weekly_report_exists(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["report_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.get_student_curator.return_value = {"user_id": 2}
    db.get_reports_for_current_week.return_value = [
        {"created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    ]

    await handler(message, state)

    assert len(message.answers) == 1
    assert "уже отправлен" in message.answers[0][0]


@pytest.mark.asyncio
async def test_report_handler_starts_new_report_flow(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["report_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.get_student_curator.return_value = {"user_id": 2}
    db.get_reports_for_current_week.return_value = []
    db.get_last_stage_choice.return_value = "stage"

    await handler(message, state)

    assert state.state == ReportStates.waiting_for_stage_selection
    assert len(message.answers) == 1
    assert "начинаем заполнение еженедельного отчета" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_problems_saves_report_and_notifies(setup_handlers):
    dispatcher, db, notification_service = setup_handlers
    handler = dispatcher.message_handlers["process_problems"]
    message = FakeMessage(user_id=5, text="problem text")
    state = FakeFSMContext()
    state.data = {
        "current_stage": "stage",
        "plans": "plans",
        "plans_completed": True,
        "plans_failure_reason": "reason",
    }
    db.save_report = AsyncMock()

    await handler(message, state)

    db.save_report.assert_awaited_once()
    assert state.cleared is True
    assert len(message.answers) == 1
    assert "отчет сохранен" in message.answers[0][0].lower()
    notification_service.notify_curator_new_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_handler_registers_new_user(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["start_handler"]
    message = FakeMessage(
        user_id=1,
        username="testuser",
        first_name="Test",
        last_name="User"
    )

    await handler(message)

    db.add_user.assert_awaited_once_with(
        user_id=1,
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    assert len(message.answers) == 1


@pytest.mark.asyncio
async def test_my_reports_handler_shows_reports(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["my_reports_handler"]
    message = FakeMessage(user_id=1)
    db.get_user_reports.return_value = [
        {
            "current_stage": "Stage 1",
            "plans": "Plans text",
            "problems": "Problems text",
            "plans_completed": True,
            "plans_failure_reason": None,
            "created_at": "2025-11-01 10:00:00"
        }
    ]
    db.get_reports_for_current_week.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "твои отчеты" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_my_reports_handler_shows_empty(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["my_reports_handler"]
    message = FakeMessage(user_id=1)
    db.get_user_reports.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "пока нет отчетов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_my_reports_handler_shows_current_week_status(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["my_reports_handler"]
    message = FakeMessage(user_id=1)
    db.get_user_reports.return_value = [
        {
            "current_stage": "Stage 1",
            "plans": "Plans",
            "problems": "Problems",
            "plans_completed": None,
            "plans_failure_reason": None,
            "created_at": "2025-11-01 10:00:00"
        }
    ]
    db.get_reports_for_current_week.return_value = [
        {
            "current_stage": "Stage 1",
            "plans": "Plans",
            "problems": "Problems",
            "created_at": "2025-11-03 10:00:00"
        }
    ]

    await handler(message)

    assert len(message.answers) == 1
    assert "уже отправлен" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_plans_validates_minimum_length(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans"]
    message = FakeMessage(user_id=1, text="abc")
    state = FakeFSMContext()
    await state.update_data(current_stage="stage")

    await handler(message, state)

    assert "минимум 5 символов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_plans_allows_cancel(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans"]
    message = FakeMessage(user_id=1, text="❌ Отменить")
    state = FakeFSMContext()
    await state.update_data(current_stage="stage")

    await handler(message, state)

    assert state.cleared is True
    assert "отменено" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_plans_accepts_valid_input(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans"]
    message = FakeMessage(user_id=1, text="Valid plans text with more than 5 characters")
    state = FakeFSMContext()
    await state.update_data(current_stage="stage")

    await handler(message, state)

    data = await state.get_data()
    assert data["plans"] == "Valid plans text with more than 5 characters"
    assert state.state == ReportStates.waiting_for_problems


@pytest.mark.asyncio
async def test_process_plans_failure_reason_validates_length(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans_failure_reason"]
    message = FakeMessage(user_id=1, text="abc")
    state = FakeFSMContext()
    await state.update_data(plans_completed=False)

    await handler(message, state)

    assert "минимум 5 символов" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_plans_failure_reason_allows_cancel(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans_failure_reason"]
    message = FakeMessage(user_id=1, text="❌ Отменить")
    state = FakeFSMContext()

    await handler(message, state)

    assert state.cleared is True
    assert "отменено" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_plans_failure_reason_accepts_valid_input(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans_failure_reason"]
    message = FakeMessage(user_id=1, text="Valid reason text")
    state = FakeFSMContext()
    await state.update_data(plans_completed=False)

    await handler(message, state)

    data = await state.get_data()
    assert data["plans_failure_reason"] == "Valid reason text"
    assert state.state == ReportStates.waiting_for_plans


@pytest.mark.asyncio
async def test_process_problems_allows_cancel(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_problems"]
    message = FakeMessage(user_id=1, text="❌ Отменить")
    state = FakeFSMContext()
    await state.update_data(current_stage="stage", plans="plans")

    await handler(message, state)

    assert state.cleared is True
    assert "отменено" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_report_handler_with_existing_weekly_report(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["report_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.get_student_curator.return_value = {"user_id": 10}
    db.get_reports_for_current_week.return_value = [
        {"created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    ]

    await handler(message, state)

    assert "уже отправлен" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_report_handler_starts_flow_for_first_report(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["report_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.get_student_curator.return_value = {"user_id": 10}
    db.get_reports_for_current_week.return_value = []
    db.get_last_stage_choice.return_value = None

    await handler(message, state)

    assert state.state == ReportStates.waiting_for_stage_selection
    assert "начинаем заполнение" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_report_handler_shows_last_stage_recommendation(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["report_handler"]
    message = FakeMessage(user_id=1)
    state = FakeFSMContext()
    db.get_student_curator.return_value = {"user_id": 10}
    db.get_reports_for_current_week.return_value = []
    db.get_last_stage_choice.return_value = "Previous stage"

    await handler(message, state)

    assert "рекомендация" in message.answers[0][0].lower()
    assert "Previous stage" in message.answers[0][0]


@pytest.mark.asyncio
async def test_process_stage_selection_text_prompts_button_use(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_stage_selection_text"]
    message = FakeMessage(user_id=1, text="some text")
    state = FakeFSMContext()
    await state.set_state(ReportStates.waiting_for_stage_selection)

    await handler(message, state)

    assert "выбери этап из предложенных кнопок" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_stage_selection_text_allows_cancel(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_stage_selection_text"]
    message = FakeMessage(user_id=1, text="❌ Отменить")
    state = FakeFSMContext()
    await state.set_state(ReportStates.waiting_for_stage_selection)

    await handler(message, state)

    assert state.cleared is True
    assert "отменено" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_plans_completion_text_prompts_button_use(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans_completion_text"]
    message = FakeMessage(user_id=1, text="some text")
    state = FakeFSMContext()
    await state.set_state(ReportStates.waiting_for_plans_completion)

    await handler(message, state)

    assert "выберите ответ из предложенных кнопок" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_process_plans_completion_text_allows_cancel(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["process_plans_completion_text"]
    message = FakeMessage(user_id=1, text="❌ Отменить")
    state = FakeFSMContext()
    await state.set_state(ReportStates.waiting_for_plans_completion)

    await handler(message, state)

    assert state.cleared is True
    assert "отменено" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_my_reports_handler_truncates_long_text(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["my_reports_handler"]
    message = FakeMessage(user_id=1)
    db.get_user_reports.return_value = [
        {
            "current_stage": "Stage 1",
            "plans": "A" * 100,
            "problems": "B" * 100,
            "plans_completed": False,
            "plans_failure_reason": "C" * 100,
            "created_at": "2025-11-01 10:00:00"
        }
    ]
    db.get_reports_for_current_week.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "..." in message.answers[0][0]


@pytest.mark.asyncio
async def test_my_reports_handler_shows_max_5_reports(setup_handlers):
    dispatcher, db, _ = setup_handlers
    handler = dispatcher.message_handlers["my_reports_handler"]
    message = FakeMessage(user_id=1)
    reports = [
        {
            "current_stage": f"Stage {i}",
            "plans": "Plans",
            "problems": "Problems",
            "plans_completed": None,
            "plans_failure_reason": None,
            "created_at": f"2025-11-0{i} 10:00:00"
        }
        for i in range(1, 8)
    ]
    db.get_user_reports.return_value = reports
    db.get_reports_for_current_week.return_value = []

    await handler(message)

    assert len(message.answers) == 1
    assert "и еще 2 отчетов" in message.answers[0][0]

