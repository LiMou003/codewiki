"""
SQLAlchemy ORM 模型 — CodeWiki 用户认证与对话历史

使用方式（示例）::

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.database.models import Base, User, UserSettings, Conversation, ConversationMessage

    engine = create_engine("postgresql+psycopg2://user:pass@localhost/codewiki")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice", email="alice@example.com", password_hash="<hashed>")
        session.add(user)
        session.commit()
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship
from sqlalchemy.sql import func


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# =============================================================
# 1. 用户账户表
# =============================================================
class User(Base):
    """用户账户表：存储用户基本认证信息。"""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="用户唯一标识（UUID）",
    )
    username = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="用户名，全局唯一，长度限制 64 字符",
    )
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="电子邮件地址，全局唯一",
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="密码的哈希值（bcrypt 等算法处理后存储，禁止明文）",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="账户是否启用；False 表示已停用或待验证",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="账户创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        comment="账户最后更新时间",
    )

    # Relationships
    settings: Mapped[Optional["UserSettings"]] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


# =============================================================
# 2. 用户配置表
# =============================================================
class UserSettings(Base):
    """用户配置表：存储用户个性化偏好，与 users 一对一关联。"""

    __tablename__ = "user_settings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="配置记录唯一标识（UUID）",
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="关联的用户 ID，外键到 users.id",
    )
    preferred_language = Column(
        String(16),
        nullable=False,
        default="zh",
        comment="界面首选语言，如 zh / en",
    )
    preferred_model = Column(
        String(128),
        nullable=True,
        comment="用户偏好使用的 AI 模型标识符",
    )
    theme = Column(
        String(16),
        nullable=False,
        default="light",
        comment="UI 主题：light / dark",
    )
    notifications_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用通知",
    )
    extra_config = Column(
        JSONB,
        nullable=True,
        comment="扩展配置（JSON），用于存储未来新增的偏好字段",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="配置创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        comment="配置最后更新时间",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings id={self.id} user_id={self.user_id}>"


# =============================================================
# 3. 对话历史表
# =============================================================
class Conversation(Base):
    """对话历史表：存储用户与 AI 的对话会话。"""

    __tablename__ = "conversations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="对话唯一标识（UUID）",
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发起对话的用户 ID，外键到 users.id",
    )
    repo_owner = Column(
        String(255),
        nullable=False,
        comment="仓库所有者（用户名或组织名）",
    )
    repo_name = Column(
        String(255),
        nullable=False,
        comment="仓库名称",
    )
    repo_type = Column(
        String(32),
        nullable=False,
        default="github",
        comment="仓库类型：github / gitlab / local 等",
    )
    title = Column(
        String(512),
        nullable=True,
        comment="对话标题，可由系统自动生成或用户手动设置",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="对话创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        comment="对话最后更新时间（有新消息时自动更新）",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} "
            f"repo={self.repo_owner}/{self.repo_name}>"
        )


# =============================================================
# 4. 对话消息表
# =============================================================
class ConversationMessage(Base):
    """对话消息表：存储对话中每条具体消息。"""

    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_conv_msg_role"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="消息唯一标识（UUID）",
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属对话 ID，外键到 conversations.id",
    )
    role = Column(
        String(16),
        nullable=False,
        comment="消息角色：user（用户提问）或 assistant（模型回答）",
    )
    content = Column(
        Text,
        nullable=False,
        comment="消息正文内容",
    )
    token_count = Column(
        Integer,
        nullable=True,
        comment="消息的 token 数量（可选，用于计费统计）",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="消息创建时间",
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationMessage id={self.id} "
            f"role={self.role!r} conversation_id={self.conversation_id}>"
        )
