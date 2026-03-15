#!/usr/bin/env python3
"""
Unit tests for api/database/models.py

Tests verify that ORM model classes are correctly defined:
- fields, types, defaults, relationships, constraints
These tests do NOT require a live database connection.
"""

import sys
import uuid
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_user_model_columns():
    """User model should define the expected columns with correct properties."""
    from sqlalchemy import inspect as sa_inspect
    from api.database.models import User

    mapper = sa_inspect(User)
    col_names = {c.key for c in mapper.columns}

    assert "id" in col_names
    assert "username" in col_names
    assert "email" in col_names
    assert "password_hash" in col_names
    assert "is_active" in col_names
    assert "created_at" in col_names
    assert "updated_at" in col_names

    id_col = mapper.columns["id"]
    assert id_col.primary_key

    username_col = mapper.columns["username"]
    assert not username_col.nullable

    email_col = mapper.columns["email"]
    assert not email_col.nullable


def test_user_settings_model_columns():
    """UserSettings model should define the expected columns."""
    from sqlalchemy import inspect as sa_inspect
    from api.database.models import UserSettings

    mapper = sa_inspect(UserSettings)
    col_names = {c.key for c in mapper.columns}

    assert "id" in col_names
    assert "user_id" in col_names
    assert "preferred_language" in col_names
    assert "preferred_model" in col_names
    assert "theme" in col_names
    assert "notifications_enabled" in col_names
    assert "extra_config" in col_names


def test_conversation_model_columns():
    """Conversation model should define the expected columns."""
    from sqlalchemy import inspect as sa_inspect
    from api.database.models import Conversation

    mapper = sa_inspect(Conversation)
    col_names = {c.key for c in mapper.columns}

    assert "id" in col_names
    assert "user_id" in col_names
    assert "repo_owner" in col_names
    assert "repo_name" in col_names
    assert "repo_type" in col_names
    assert "title" in col_names
    assert "created_at" in col_names
    assert "updated_at" in col_names


def test_conversation_message_model_columns():
    """ConversationMessage model should define the expected columns."""
    from sqlalchemy import inspect as sa_inspect
    from api.database.models import ConversationMessage

    mapper = sa_inspect(ConversationMessage)
    col_names = {c.key for c in mapper.columns}

    assert "id" in col_names
    assert "conversation_id" in col_names
    assert "role" in col_names
    assert "content" in col_names
    assert "token_count" in col_names
    assert "created_at" in col_names


def test_user_model_instantiation():
    """User model should be instantiable without a DB connection."""
    from api.database.models import User

    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="$2b$12$fakehash",
        is_active=True,
    )
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True


def test_user_settings_instantiation():
    """UserSettings model should be instantiable with explicit values."""
    from api.database.models import UserSettings

    uid = uuid.uuid4()
    settings = UserSettings(
        user_id=uid,
        preferred_language="zh",
        theme="light",
        notifications_enabled=True,
    )
    assert settings.user_id == uid
    assert settings.preferred_language == "zh"
    assert settings.theme == "light"
    assert settings.notifications_enabled is True


def test_conversation_instantiation():
    """Conversation model should be instantiable with explicit values."""
    from api.database.models import Conversation

    uid = uuid.uuid4()
    conv = Conversation(
        user_id=uid,
        repo_owner="octocat",
        repo_name="Hello-World",
        repo_type="github",
    )
    assert conv.user_id == uid
    assert conv.repo_owner == "octocat"
    assert conv.repo_name == "Hello-World"
    assert conv.repo_type == "github"


def test_conversation_message_instantiation():
    """ConversationMessage model should be instantiable."""
    from api.database.models import ConversationMessage

    cid = uuid.uuid4()
    msg = ConversationMessage(
        conversation_id=cid,
        role="user",
        content="Hello, AI!",
    )
    assert msg.conversation_id == cid
    assert msg.role == "user"
    assert msg.content == "Hello, AI!"
    assert msg.token_count is None


def test_user_relationships_defined():
    """User model should expose 'settings' and 'conversations' relationships."""
    from api.database.models import User

    user = User(
        username="rel_test",
        email="rel@example.com",
        password_hash="hash",
    )
    # Accessing relationship attributes should not raise before flush/commit
    assert hasattr(user, "settings")
    assert hasattr(user, "conversations")


def test_table_names():
    """ORM models should use the correct __tablename__ values."""
    from api.database.models import (
        User,
        UserSettings,
        Conversation,
        ConversationMessage,
    )

    assert User.__tablename__ == "users"
    assert UserSettings.__tablename__ == "user_settings"
    assert Conversation.__tablename__ == "conversations"
    assert ConversationMessage.__tablename__ == "conversation_messages"


def test_package_exports():
    """api.database package should re-export all models."""
    from api.database import (
        Base,
        Conversation,
        ConversationMessage,
        User,
        UserSettings,
    )

    assert Base is not None
    assert User.__tablename__ == "users"
    assert UserSettings.__tablename__ == "user_settings"
    assert Conversation.__tablename__ == "conversations"
    assert ConversationMessage.__tablename__ == "conversation_messages"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
