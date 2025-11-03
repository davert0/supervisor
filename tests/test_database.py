import asyncio
from datetime import datetime, timedelta

import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_add_user_and_get_profile(db):
    await db.add_user(1, username="student", first_name="Ivan", last_name="Ivanov")

    profile = await db.get_user_profile(1)

    assert profile == {
        "user_id": 1,
        "username": "student",
        "first_name": "Ivan",
        "last_name": "Ivanov",
    }


@pytest.mark.asyncio
async def test_get_all_active_users_filters_only_active_students(db):
    await db.add_user(1, username="active_student", user_type="student")
    await db.add_user(2, username="curator", user_type="curator")
    await db.add_user(3, username="inactive_student", user_type="student")

    async with aiosqlite.connect(db.db_path) as connection:
        await connection.execute(
            "update users set is_active = false where user_id = ?",
            (3,),
        )
        await connection.commit()

    users = await db.get_all_active_users()

    assert len(users) == 1
    assert users[0]["user_id"] == 1


@pytest.mark.asyncio
async def test_save_report_and_get_user_reports_sorted(db):
    await db.add_user(1, username="student", user_type="student")

    await db.save_report(1, "stage1", "plan1", "problem1")
    async with aiosqlite.connect(db.db_path) as connection:
        older = datetime.now() - timedelta(minutes=5)
        await connection.execute(
            "update reports set created_at = ? where user_id = ? and current_stage = ?",
            (older.strftime("%Y-%m-%d %H:%M:%S"), 1, "stage1"),
        )
        await connection.commit()
    await db.save_report(1, "stage2", "plan2", "problem2")

    reports = await db.get_user_reports(1)

    assert len(reports) == 2
    stages = {report["current_stage"] for report in reports}
    assert stages == {"stage1", "stage2"}
    first_time = datetime.fromisoformat(reports[0]["created_at"])
    second_time = datetime.fromisoformat(reports[1]["created_at"])
    assert first_time >= second_time


@pytest.mark.asyncio
async def test_mark_report_as_read_filters_by_curator(db):
    await db.add_user(10, username="curator", first_name="Cur", last_name="Ator", user_type="curator")
    await db.add_user(1, username="student1", first_name="Stu", last_name="Dent", user_type="student")
    await db.add_user(2, username="student2", user_type="student")

    await db.add_curator_student_relation(10, 1)
    await db.add_curator_student_relation(10, 2)

    await db.save_report(1, "stage1", "plan1", "problem1")
    await db.save_report(2, "stage2", "plan2", "problem2")

    unread_before = await db.get_unread_reports_for_curator(10)
    assert len(unread_before) == 2

    await db.mark_report_as_read(unread_before[0]["id"], 10)

    unread_after = await db.get_unread_reports_for_curator(10)
    assert len(unread_after) == 1


@pytest.mark.asyncio
async def test_get_students_missing_weekly_reports_returns_students_without_reports(db):
    await db.add_user(10, username="curator", first_name="Cur", last_name="Ator", user_type="curator")
    await db.add_user(1, username="student1", first_name="Stu", last_name="Dent", user_type="student")
    await db.add_user(2, username="student2", user_type="student")

    await db.add_curator_student_relation(10, 1)
    await db.add_curator_student_relation(10, 2)

    await db.save_report(2, "stage", "plan", "problem")

    async with aiosqlite.connect(db.db_path) as connection:
        past_date = datetime.now() - timedelta(days=14)
        await connection.execute(
            "update reports set created_at = ? where user_id = ?",
            (past_date.strftime("%Y-%m-%d %H:%M:%S"), 2),
        )
        await connection.commit()

    missing = await db.get_students_missing_weekly_reports()

    assert len(missing) == 2
    student_ids = {record["student_id"] for record in missing}
    assert student_ids == {1, 2}


@pytest.mark.asyncio
async def test_has_previous_reports_returns_true_when_reports_exist(db):
    await db.add_user(1, username="student", user_type="student")
    await db.save_report(1, "stage1", "plan1", "problem1")
    
    has_reports = await db.has_previous_reports(1)
    
    assert has_reports is True


@pytest.mark.asyncio
async def test_has_previous_reports_returns_false_when_no_reports(db):
    await db.add_user(1, username="student", user_type="student")
    
    has_reports = await db.has_previous_reports(1)
    
    assert has_reports is False


@pytest.mark.asyncio
async def test_get_last_stage_choice_returns_most_recent_stage(db):
    await db.add_user(1, username="student", user_type="student")
    await db.save_report(1, "stage1", "plan1", "problem1")
    
    async with aiosqlite.connect(db.db_path) as connection:
        older = datetime.now() - timedelta(days=1)
        await connection.execute(
            "update reports set created_at = ? where current_stage = ?",
            (older.strftime("%Y-%m-%d %H:%M:%S"), "stage1"),
        )
        await connection.commit()
    
    await db.save_report(1, "stage2", "plan2", "problem2")
    
    async with aiosqlite.connect(db.db_path) as connection:
        cursor = await connection.execute(
            "select current_stage, created_at from reports where user_id = ? order by created_at desc",
            (1,)
        )
        rows = await cursor.fetchall()
    
    last_stage = await db.get_last_stage_choice(1)
    
    assert last_stage == "stage2"


@pytest.mark.asyncio
async def test_get_last_stage_choice_returns_none_when_no_reports(db):
    await db.add_user(1, username="student", user_type="student")
    
    last_stage = await db.get_last_stage_choice(1)
    
    assert last_stage is None


@pytest.mark.asyncio
async def test_is_admin_returns_true_for_admin_id(db, monkeypatch):
    monkeypatch.setenv("ADMIN_ID", "123")
    
    result = await db.is_admin(123)
    
    assert result is True


@pytest.mark.asyncio
async def test_is_admin_returns_false_for_non_admin(db, monkeypatch):
    monkeypatch.setenv("ADMIN_ID", "123")
    
    result = await db.is_admin(456)
    
    assert result is False


@pytest.mark.asyncio
async def test_is_admin_returns_false_when_no_env_variable(db, monkeypatch):
    monkeypatch.delenv("ADMIN_ID", raising=False)
    
    result = await db.is_admin(123)
    
    assert result is False


@pytest.mark.asyncio
async def test_is_admin_returns_false_when_invalid_env_value(db, monkeypatch):
    monkeypatch.setenv("ADMIN_ID", "invalid")
    
    result = await db.is_admin(123)
    
    assert result is False


@pytest.mark.asyncio
async def test_activate_curator(db):
    await db.add_user(10, username="curator", user_type="curator")
    await db.deactivate_curator(10)
    
    await db.activate_curator(10)
    
    async with aiosqlite.connect(db.db_path) as connection:
        cursor = await connection.execute(
            "select is_active from users where user_id = ?",
            (10,)
        )
        row = await cursor.fetchone()
        assert row[0] == 1


@pytest.mark.asyncio
async def test_deactivate_curator(db):
    await db.add_user(10, username="curator", user_type="curator")
    
    await db.deactivate_curator(10)
    
    async with aiosqlite.connect(db.db_path) as connection:
        cursor = await connection.execute(
            "select is_active from users where user_id = ?",
            (10,)
        )
        row = await cursor.fetchone()
        assert row[0] == 0


@pytest.mark.asyncio
async def test_assign_student_to_curator_creates_relation(db):
    await db.add_user(1, username="student", user_type="student")
    await db.add_user(10, username="curator", user_type="curator")
    
    await db.assign_student_to_curator(1, 10)
    
    curator = await db.get_student_curator(1)
    assert curator is not None
    assert curator["user_id"] == 10


@pytest.mark.asyncio
async def test_assign_student_to_curator_creates_multiple_relations(db):
    await db.add_user(1, username="student", user_type="student")
    await db.add_user(10, username="curator1", user_type="curator")
    await db.add_user(20, username="curator2", user_type="curator")
    
    await db.assign_student_to_curator(1, 10)
    await db.assign_student_to_curator(1, 20)
    
    curator = await db.get_student_curator(1)
    assert curator is not None
    assert curator["user_id"] in [10, 20]


@pytest.mark.asyncio
async def test_get_all_curators_returns_only_active(db):
    await db.add_user(10, username="curator1", first_name="Cur1", last_name="Ator1", user_type="curator")
    await db.add_user(20, username="curator2", first_name="Cur2", last_name="Ator2", user_type="curator")
    await db.deactivate_curator(20)
    
    curators = await db.get_all_curators()
    
    assert len(curators) == 1
    assert curators[0]["user_id"] == 10


@pytest.mark.asyncio
async def test_get_curator_students_returns_only_active_students(db):
    await db.add_user(10, username="curator", user_type="curator")
    await db.add_user(1, username="student1", first_name="Stu1", last_name="Dent1", user_type="student")
    await db.add_user(2, username="student2", first_name="Stu2", last_name="Dent2", user_type="student")
    await db.add_curator_student_relation(10, 1)
    await db.add_curator_student_relation(10, 2)
    
    async with aiosqlite.connect(db.db_path) as connection:
        await connection.execute(
            "update users set is_active = false where user_id = ?",
            (2,)
        )
        await connection.commit()
    
    students = await db.get_curator_students(10)
    
    assert len(students) == 1
    assert students[0]["user_id"] == 1


@pytest.mark.asyncio
async def test_get_report_by_id_returns_report(db):
    await db.add_user(1, username="student", user_type="student")
    await db.save_report(1, "stage1", "plan1", "problem1")
    
    async with aiosqlite.connect(db.db_path) as connection:
        cursor = await connection.execute("select id from reports where user_id = ?", (1,))
        row = await cursor.fetchone()
        report_id = row[0]
    
    report = await db.get_report_by_id(report_id)
    
    assert report is not None
    assert report["user_id"] == 1
    assert report["current_stage"] == "stage1"


@pytest.mark.asyncio
async def test_get_report_by_id_returns_none_when_not_found(db):
    report = await db.get_report_by_id(999)
    
    assert report is None


@pytest.mark.asyncio
async def test_get_students_without_curators_excludes_students_with_curators(db):
    await db.add_user(1, username="student1", first_name="Stu1", last_name="Dent1", user_type="student")
    await db.add_user(2, username="student2", first_name="Stu2", last_name="Dent2", user_type="student")
    await db.add_user(10, username="curator", user_type="curator")
    await db.add_curator_student_relation(10, 1)
    
    students = await db.get_students_without_curators()
    
    assert len(students) == 1
    assert students[0]["user_id"] == 2


@pytest.mark.asyncio
async def test_get_user_type_returns_student_by_default(db):
    user_type = await db.get_user_type(999)
    
    assert user_type == "student"


@pytest.mark.asyncio
async def test_get_user_type_returns_correct_type(db):
    await db.add_user(10, username="curator", user_type="curator")
    
    user_type = await db.get_user_type(10)
    
    assert user_type == "curator"


@pytest.mark.asyncio
async def test_get_all_student_reports_for_curator_returns_reports(db):
    await db.add_user(10, username="curator", first_name="Cur", last_name="Ator", user_type="curator")
    await db.add_user(1, username="student1", first_name="Stu", last_name="Dent", user_type="student")
    await db.add_user(2, username="student2", user_type="student")
    
    await db.add_curator_student_relation(10, 1)
    await db.add_curator_student_relation(10, 2)
    
    await db.save_report(1, "stage1", "plan1", "problem1", plans_completed=True)
    await db.save_report(1, "stage2", "plan2", "problem2", plans_completed=False, plans_failure_reason="reason")
    await db.save_report(2, "stage3", "plan3", "problem3")
    
    reports = await db.get_all_student_reports_for_curator(10, 1)
    
    assert len(reports) == 2
    assert all(r["user_id"] == 1 for r in reports)
    stages = {r["current_stage"] for r in reports}
    assert stages == {"stage1", "stage2"}
    stage1_report = next(r for r in reports if r["current_stage"] == "stage1")
    stage2_report = next(r for r in reports if r["current_stage"] == "stage2")
    assert stage1_report["plans_completed"] is True
    assert stage2_report["plans_completed"] is False
    assert stage2_report["plans_failure_reason"] == "reason"
    assert "Stu Dent" in reports[0]["student_name"]


@pytest.mark.asyncio
async def test_get_all_student_reports_for_curator_returns_empty_for_no_reports(db):
    await db.add_user(10, username="curator", user_type="curator")
    await db.add_user(1, username="student1", user_type="student")
    
    await db.add_curator_student_relation(10, 1)
    
    reports = await db.get_all_student_reports_for_curator(10, 1)
    
    assert len(reports) == 0


@pytest.mark.asyncio
async def test_get_all_student_reports_for_curator_checks_access(db):
    await db.add_user(10, username="curator1", user_type="curator")
    await db.add_user(20, username="curator2", user_type="curator")
    await db.add_user(1, username="student1", user_type="student")
    
    await db.add_curator_student_relation(10, 1)
    await db.save_report(1, "stage1", "plan1", "problem1")
    
    reports_curator1 = await db.get_all_student_reports_for_curator(10, 1)
    reports_curator2 = await db.get_all_student_reports_for_curator(20, 1)
    
    assert len(reports_curator1) == 1
    assert len(reports_curator2) == 0


@pytest.mark.asyncio
async def test_get_all_student_reports_for_curator_includes_read_status(db):
    await db.add_user(10, username="curator", user_type="curator")
    await db.add_user(1, username="student1", user_type="student")
    
    await db.add_curator_student_relation(10, 1)
    await db.save_report(1, "stage1", "plan1", "problem1")
    
    async with aiosqlite.connect(db.db_path) as connection:
        cursor = await connection.execute("select id from reports where user_id = ?", (1,))
        row = await cursor.fetchone()
        report_id = row[0]
    
    await db.mark_report_as_read(report_id, 10)
    
    reports = await db.get_all_student_reports_for_curator(10, 1)
    
    assert len(reports) == 1
    assert reports[0]["is_read_by_curator"] is True

