"""
api/database 包初始化

提供共享的数据库基础设施，包括异步引擎、会话工厂和表初始化。
所有需要访问数据库的模块（auth_router, conversation_router 等）
都应该从此处导入 get_db / init_db，确保使用统一的数据库连接。

Usage::

    from api.database import get_db, init_db

Datbase URL 配置：
    通过环境变量 AUTH_DATABASE_URL 指定，默认为项目目录下的 SQLite 文件。
"""

import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from api.database.models import (
    Base,
    Conversation,
    ConversationMessage,
    User,
    UserSettings,
)

logger = logging.getLogger(__name__)

__all__ = [
    "Base",
    "User",
    "UserSettings",
    "Conversation",
    "ConversationMessage",
    "get_db",
    "init_db",
]

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "codewiki_auth.db")
DATABASE_URL = os.environ.get("AUTH_DATABASE_URL", f"sqlite+aiosqlite:///{_DB_PATH}")

_engine_kwargs: dict = {"echo": False, "future": True}
if DATABASE_URL.startswith("mysql"):
    _engine_kwargs.update({"pool_recycle": 3600, "pool_pre_ping": True})

_engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
_AsyncSession = async_sessionmaker(_engine, expire_on_commit=False)


async def init_db() -> None:
    """Create tables if they don't exist yet."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with _AsyncSession() as session:
        yield session
