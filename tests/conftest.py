import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import database as database_module
from database import Database


@pytest.fixture(scope="function")
async def db(tmp_path, monkeypatch) -> AsyncGenerator[Database, None]:
    test_db_path = tmp_path / "reports.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(test_db_path))
    monkeypatch.setattr(database_module, "DATABASE_PATH", str(test_db_path))
    database = Database()
    database.db_path = str(test_db_path)
    await database.init_db()
    yield database

