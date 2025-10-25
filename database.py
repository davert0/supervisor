import aiosqlite
from datetime import datetime
from typing import List, Optional
from config import DATABASE_PATH

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                create table if not exists users (
                    id integer primary key,
                    user_id integer unique not null,
                    username text,
                    first_name text,
                    last_name text,
                    is_active boolean default true,
                    created_at timestamp default current_timestamp
                )
            ''')
            
            await db.execute('''
                create table if not exists reports (
                    id integer primary key autoincrement,
                    user_id integer not null,
                    report_text text not null,
                    created_at timestamp default current_timestamp,
                    foreign key (user_id) references users (user_id)
                )
            ''')
            
            await db.commit()

    async def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                insert or replace into users (user_id, username, first_name, last_name)
                values (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            await db.commit()

    async def get_all_active_users(self) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select user_id, username, first_name, last_name 
                from users 
                where is_active = true
            ''')
            rows = await cursor.fetchall()
            return [{'user_id': row[0], 'username': row[1], 'first_name': row[2], 'last_name': row[3]} for row in rows]

    async def save_report(self, user_id: int, report_text: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                insert into reports (user_id, report_text)
                values (?, ?)
            ''', (user_id, report_text))
            await db.commit()

    async def get_user_reports(self, user_id: int) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                select report_text, created_at 
                from reports 
                where user_id = ? 
                order by created_at desc
            ''', (user_id,))
            rows = await cursor.fetchall()
            return [{'text': row[0], 'created_at': row[1]} for row in rows]

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
