from aiogram.fsm.state import State, StatesGroup

class ReportStates(StatesGroup):
    waiting_for_stage_selection = State()
    waiting_for_plans = State()
    waiting_for_plans_completion = State()
    waiting_for_plans_failure_reason = State()
    waiting_for_problems = State()

class CuratorStates(StatesGroup):
    waiting_for_student_id = State()

class AdminStates(StatesGroup):
    waiting_for_curator_id = State()
    waiting_for_curator_username = State()
    waiting_for_curator_name = State()
    waiting_for_student_to_assign = State()
    waiting_for_curator_to_assign = State()
    waiting_for_student_id = State()
