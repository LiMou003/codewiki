"""
User settings router.

GET  /api/user/settings  — read current user's settings
PUT  /api/user/settings  — update current user's settings
"""

import copy
import json
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.database.models import User as UserRow, UserSettings as UserSettingsRow
from api.auth_router import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: Dict[str, Any] = {
    "embedding": {"dimension": 1024},
    "retrieval": {"top_k": 20},
    "auto_refresh": {"enabled": True, "interval_minutes": 60},
}

_SUB_CONFIG_KEYS = ("embedding", "retrieval", "auto_refresh")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserSettingsOut(BaseModel):
    config: Optional[Dict[str, Any]] = None


class UserSettingsUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_dict(raw) -> dict:
    """Ensure *raw* is a dict.  Always returns a fresh deep-copy so that
    SQLAlchemy's identity check detects the mutation on commit."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Stored config is not valid JSON: %s", raw[:200])
            return {}
    return {}


def _row_config(row: UserSettingsRow) -> dict:
    stored = _ensure_dict(row.extra_config)
    filtered = {}
    for k in _SUB_CONFIG_KEYS:
        if k in stored and isinstance(stored[k], dict):
            filtered[k] = stored[k]
    return filtered


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=UserSettingsOut)
async def get_user_settings(
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSettingsRow).where(UserSettingsRow.user_id == current_user.id)
    )
    row = result.scalars().first()

    if row is None:
        return UserSettingsOut(config=dict(_DEFAULT_CONFIG))

    stored = _row_config(row)
    return UserSettingsOut(config=stored if stored else dict(_DEFAULT_CONFIG))


@router.put("/settings", response_model=UserSettingsOut)
async def update_user_settings(
    body: UserSettingsUpdate,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSettingsRow).where(UserSettingsRow.user_id == current_user.id)
    )
    row = result.scalars().first()

    if row is None:
        from uuid import uuid4

        row = UserSettingsRow(
            id=str(uuid4()),
            user_id=current_user.id,
        )
        db.add(row)

    if body.config and isinstance(body.config, dict):
        stored = _ensure_dict(row.extra_config)
        logger.info("PUT /settings: existing=%s incoming=%s", list(stored.keys()), list(body.config.keys()))

        for section in _SUB_CONFIG_KEYS:
            if section in body.config and isinstance(body.config[section], dict):
                if section not in stored or not isinstance(stored.get(section), dict):
                    stored[section] = {}
                stored[section].update(body.config[section])
                logger.info("PUT /settings: updated %s → %s", section, stored[section])

        row.extra_config = stored if stored else None
        await db.commit()
        await db.refresh(row)

    stored = _row_config(row)
    return UserSettingsOut(config=stored if stored else dict(_DEFAULT_CONFIG))


# ---------------------------------------------------------------------------
# Shared helper used by other modules
# ---------------------------------------------------------------------------


async def get_user_top_k(user_id: str, db: AsyncSession, default: int = 20) -> int:
    result = await db.execute(
        select(UserSettingsRow).where(UserSettingsRow.user_id == user_id)
    )
    row = result.scalars().first()
    if row is None or row.extra_config is None:
        return default
    stored = _ensure_dict(row.extra_config)
    try:
        return int((stored.get("retrieval") or {}).get("top_k", default))
    except (TypeError, ValueError):
        return default


async def read_user_dimension_from_db() -> Optional[int]:
    """Read embedding dimension directly from the user_settings table.

    Opens its own DB session — usable from non-FastAPI contexts (e.g. WebSocket
    handlers) where ``get_db`` / ``get_current_user`` dependencies are unavailable.
    Returns ``None`` if no dimension has been saved by any user.
    """
    try:
        from api.database import _AsyncSession as AsyncSess

        async with AsyncSess() as session:
            result = await session.execute(
                select(UserSettingsRow).limit(1)
            )
            row = result.scalars().first()
            if row is None:
                return None
            stored = _ensure_dict(row.extra_config)
            dim = (stored.get("embedding") or {}).get("dimension")
            if dim is not None:
                logger.debug("Read user dimension=%d from database", dim)
                return int(dim)
            return None
    except Exception as exc:
        logger.warning("Could not read user dimension from DB: %s", exc)
        return None
