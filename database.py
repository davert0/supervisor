import os
import aiosqlite
from datetime import datetime, timedelta
from typing import List, Optional
from config import DATABASE_PATH

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH

    async def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                create table if not exists users (
                    id integer primary key,
                    user_id integer unique not null,
                    username text,
                    first_name text,
                    last_name text,
                    is_active boolean default true,
                    user_type text default 'student',
                    created_at timestamp default current_timestamp
                )
            ''')
            
            await db.execute('''
                create table if not exists reports (
                    id integer primary key autoincrement,
                    user_id integer not null,
                    current_stage text not null,
                    plans text not null,
                    plans_completed boolean,
                    plans_failure_reason text,
                    problems text not null,
                    is_read_by_curator boolean default false,
                    created_at timestamp default current_timestamp,
                    foreign key (user_id) references users (user_id)
                )
            ''')
            
            await db.execute('''
                create table if not exists curator_student_relations (
                    id integer primary key autoincrement,
                    curator_id integer not null,
                    student_id integer not null,
                    created_at timestamp default current_timestamp,
                    foreign key (curator_id) references users (user_id),
                    foreign key (student_id) references users (user_id),
                    unique(curator_id, student_id)
                )
            ''')
            
            await db.commit()

    async def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None, user_type: str = 'student'):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                insert or replace into users (user_id, username, first_name, last_name, user_type)
                values (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, user_type))
            await db.commit()

    async def get_all_active_users(self) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select user_id, username, first_name, last_name 
                from users 
                where is_active = true and user_type = 'student'
            ''')
            rows = await cursor.fetchall()
            return [{'user_id': row[0], 'username': row[1], 'first_name': row[2], 'last_name': row[3]} for row in rows]

    async def save_report(self, user_id: int, current_stage: str, plans: str, problems: str, plans_completed: bool = None, plans_failure_reason: str = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                insert into reports (user_id, current_stage, plans, problems, plans_completed, plans_failure_reason)
                values (?, ?, ?, ?, ?, ?)
            ''', (user_id, current_stage, plans, problems, plans_completed, plans_failure_reason))
            await db.commit()

    async def get_user_reports(self, user_id: int) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select current_stage, plans, problems, plans_completed, plans_failure_reason, created_at 
                from reports 
                where user_id = ? 
                order by created_at desc
            ''', (user_id,))
            rows = await cursor.fetchall()
            return [{
                'current_stage': row[0], 'plans': row[1], 'problems': row[2], 
                'plans_completed': row[3], 'plans_failure_reason': row[4], 'created_at': row[5]
            } for row in rows]

    async def get_last_report_date(self, user_id: int) -> Optional[datetime]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select created_at 
                from reports 
                where user_id = ? 
                order by created_at desc 
                limit 1
            ''', (user_id,))
            row = await cursor.fetchone()
            if row:
                return datetime.fromisoformat(row[0])
            return None

    async def get_reports_for_current_week(self, user_id: int) -> List[dict]:
        """Получает отчеты пользователя за текущую календарную неделю"""
        # Находим начало текущей недели (понедельник)
        today = datetime.now().date()
        days_since_monday = today.weekday()  # 0 = понедельник, 6 = воскресенье
        week_start = today - timedelta(days=days_since_monday)
        week_start_datetime = datetime.combine(week_start, datetime.min.time())
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select current_stage, plans, problems, created_at 
                from reports 
                where user_id = ? and created_at >= ?
                order by created_at desc
            ''', (user_id, week_start_datetime.isoformat()))
            rows = await cursor.fetchall()
            return [{'current_stage': row[0], 'plans': row[1], 'problems': row[2], 'created_at': row[3]} for row in rows]

    async def get_students_missing_weekly_reports(self) -> List[dict]:
        today = datetime.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_start_datetime = datetime.combine(week_start, datetime.min.time())

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select
                    csr.curator_id,
                    c.username,
                    c.first_name,
                    c.last_name,
                    s.user_id,
                    s.username,
                    s.first_name,
                    s.last_name
                from curator_student_relations csr
                join users c on csr.curator_id = c.user_id and c.is_active = true
                join users s on csr.student_id = s.user_id and s.is_active = true
                left join reports r on r.user_id = s.user_id and r.created_at >= ?
                group by csr.curator_id, c.username, c.first_name, c.last_name, s.user_id, s.username, s.first_name, s.last_name
                having max(r.created_at) is null
                order by csr.curator_id, s.first_name, s.last_name
            ''', (week_start_datetime.isoformat(),))
            rows = await cursor.fetchall()
            return [
                {
                    'curator_id': row[0],
                    'curator_username': row[1],
                    'curator_first_name': row[2],
                    'curator_last_name': row[3],
                    'student_id': row[4],
                    'student_username': row[5],
                    'student_first_name': row[6],
                    'student_last_name': row[7]
                }
                for row in rows
            ]

    async def get_last_stage_choice(self, user_id: int) -> Optional[str]:
        """Получает последний выбранный этап пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select current_stage 
                from reports 
                where user_id = ? 
                order by created_at desc 
                limit 1
            ''', (user_id,))
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None

    async def has_previous_reports(self, user_id: int) -> bool:
        """Проверяет, есть ли у пользователя предыдущие отчеты"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select count(*) 
                from reports 
                where user_id = ?
            ''', (user_id,))
            row = await cursor.fetchone()
            return row[0] > 0

    async def add_curator_student_relation(self, curator_id: int, student_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                insert or ignore into curator_student_relations (curator_id, student_id)
                values (?, ?)
            ''', (curator_id, student_id))
            await db.commit()

    async def get_curator_students(self, curator_id: int) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select u.user_id, u.username, u.first_name, u.last_name
                from users u
                join curator_student_relations csr on u.user_id = csr.student_id
                where csr.curator_id = ? and u.is_active = true
            ''', (curator_id,))
            rows = await cursor.fetchall()
            return [{'user_id': row[0], 'username': row[1], 'first_name': row[2], 'last_name': row[3]} for row in rows]

    async def get_student_curator(self, student_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select u.user_id, u.username, u.first_name, u.last_name
                from users u
                join curator_student_relations csr on u.user_id = csr.curator_id
                where csr.student_id = ? and u.is_active = true
            ''', (student_id,))
            row = await cursor.fetchone()
            if row:
                return {'user_id': row[0], 'username': row[1], 'first_name': row[2], 'last_name': row[3]}
            return None

    async def get_unread_reports_for_curator(self, curator_id: int) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select r.id, r.user_id, r.current_stage, r.plans, r.problems, r.created_at,
                       u.first_name, u.last_name, u.username
                from reports r
                join users u on r.user_id = u.user_id
                join curator_student_relations csr on u.user_id = csr.student_id
                where csr.curator_id = ? and r.is_read_by_curator = false
                order by r.created_at desc
            ''', (curator_id,))
            rows = await cursor.fetchall()
            return [{
                'id': row[0], 'user_id': row[1], 'current_stage': row[2], 
                'plans': row[3], 'problems': row[4], 'created_at': row[5],
                'student_name': f"{row[6]} {row[7]}" if row[6] and row[7] else row[8] or f"ID: {row[1]}"
            } for row in rows]

    async def mark_report_as_read(self, report_id: int, curator_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                update reports 
                set is_read_by_curator = true 
                where id = ? and user_id in (
                    select student_id from curator_student_relations 
                    where curator_id = ?
                )
            ''', (report_id, curator_id))
            await db.commit()

    async def get_report_by_id(self, report_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select user_id, current_stage, plans, problems, created_at
                from reports 
                where id = ?
            ''', (report_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    'user_id': row[0], 'current_stage': row[1], 
                    'plans': row[2], 'problems': row[3], 'created_at': row[4]
                }
            return None

    async def get_all_students_with_curators(self) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select 
                    u.user_id, u.username, u.first_name, u.last_name,
                    c.user_id as curator_id, c.username as curator_username, 
                    c.first_name as curator_first_name, c.last_name as curator_last_name
                from users u
                left join curator_student_relations csr on u.user_id = csr.student_id
                left join users c on csr.curator_id = c.user_id
                where u.user_type = 'student' and u.is_active = true
                order by u.first_name, u.last_name
            ''')
            rows = await cursor.fetchall()
            return [{
                'user_id': row[0], 'username': row[1], 'first_name': row[2], 'last_name': row[3],
                'curator_id': row[4], 'curator_username': row[5], 
                'curator_first_name': row[6], 'curator_last_name': row[7]
            } for row in rows]

    async def get_user_type(self, user_id: int) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'select user_type from users where user_id = ?', (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 'student'

    async def get_all_curators(self) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select user_id, username, first_name, last_name, created_at
                from users 
                where user_type = 'curator' and is_active = true
                order by first_name, last_name
            ''')
            rows = await cursor.fetchall()
            return [{
                'user_id': row[0], 'username': row[1], 'first_name': row[2], 
                'last_name': row[3], 'created_at': row[4]
            } for row in rows]

    async def get_curator_stats(self, curator_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select count(distinct csr.student_id) as student_count,
                       count(r.id) as total_reports,
                       count(case when r.is_read_by_curator = false then 1 end) as unread_reports
                from curator_student_relations csr
                left join reports r on csr.student_id = r.user_id
                where csr.curator_id = ?
            ''', (curator_id,))
            row = await cursor.fetchone()
            return {
                'student_count': row[0] or 0,
                'total_reports': row[1] or 0,
                'unread_reports': row[2] or 0
            }

    async def remove_curator_student_relation(self, curator_id: int, student_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                delete from curator_student_relations 
                where curator_id = ? and student_id = ?
            ''', (curator_id, student_id))
            await db.commit()

    async def deactivate_curator(self, curator_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                update users 
                set is_active = false 
                where user_id = ? and user_type = 'curator'
            ''', (curator_id,))
            await db.commit()

    async def activate_curator(self, curator_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                update users 
                set is_active = true 
                where user_id = ? and user_type = 'curator'
            ''', (curator_id,))
            await db.commit()

    async def get_students_without_curators(self) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select u.user_id, u.username, u.first_name, u.last_name
                from users u
                left join curator_student_relations csr on u.user_id = csr.student_id
                where u.user_type = 'student' and u.is_active = true and csr.student_id is null
                order by u.first_name, u.last_name
            ''')
            rows = await cursor.fetchall()
            return [{'user_id': row[0], 'username': row[1], 'first_name': row[2], 'last_name': row[3]} for row in rows]

    async def assign_student_to_curator(self, student_id: int, curator_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                insert or replace into curator_student_relations (curator_id, student_id)
                values (?, ?)
            ''', (curator_id, student_id))
            await db.commit()

    async def is_admin(self, user_id: int) -> bool:
        admin_id_value = os.getenv('ADMIN_ID')
        if not admin_id_value:
            return False
        try:
            return user_id == int(admin_id_value)
        except ValueError:
            return False
