"""
Authentication router for CodeWiki.

Provides:
    POST /auth/register  — create a new user account
    POST /auth/login     — obtain a JWT access token
    GET  /auth/me        — return the authenticated user's profile (requires JWT)

Storage: MySQL (or SQLite fallback) via SQLAlchemy async engine.
Set AUTH_DATABASE_URL to connect to your local MySQL database, e.g.:
    mysql+aiomysql://user:password@localhost/codewiki
Passwords are hashed with PBKDF2-SHA256.  Tokens are signed JWTs (HS256).
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.database.models import Base, User as _UserRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DEFAULT_SECRET = "change-me-in-production-use-a-long-random-secret"
JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", _DEFAULT_SECRET)
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

# MySQL database connection (falls back to SQLite for local development without MySQL)
_DB_PATH = os.path.join(os.path.dirname(__file__), "codewiki_auth.db")
DATABASE_URL = os.environ.get("AUTH_DATABASE_URL", f"sqlite+aiosqlite:///{_DB_PATH}")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Build engine kwargs depending on dialect
_engine_kwargs: dict = {"echo": False, "future": True}
if DATABASE_URL.startswith("mysql"):
    # Recommended pool settings for MySQL async connections
    _engine_kwargs.update({"pool_recycle": 3600, "pool_pre_ping": True})

_engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
_AsyncSession = async_sessionmaker(_engine, expire_on_commit=False)


async def init_db() -> None:
    """Create tables if they don't exist yet."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[override]
    async with _AsyncSession() as session:
        yield session


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


def _hash_password(plain: str) -> str:
    # PBKDF2-SHA256 has no 72-byte bcrypt limit
    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


def _create_access_token(
    subject: str, expires_delta: Optional[timedelta] = None
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "iat": now, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> str:
    """Return the subject (user id) from a valid token or raise HTTPException."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        subject: Optional[str] = payload.get("sub")
        if subject is None:
            raise JWTError("missing sub")
        return subject
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或已过期的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def _get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> _UserRow:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = _decode_token(credentials.credentials)
    result = await db.execute(select(_UserRow).where(_UserRow.id == user_id))
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已停用",
        )
    return user


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: EmailStr = Field(..., description="电子邮箱")
    password: str = Field(..., min_length=8, description="密码（至少 8 个字符）")


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/auth", tags=["auth"])

# def get_adalflow_default_root_path():
#     return os.path.expanduser(os.path.join("~", ".adalflow"))

# WIKI_CACHE_DIR = os.path.join(get_adalflow_default_root_path(), "wikicache")

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user and return a JWT access token."""
    # Check uniqueness
    dup = await db.execute(
        select(_UserRow).where(
            (_UserRow.username == body.username) | (_UserRow.email == body.email)
        )
    )
    existing = dup.scalars().first()
    if existing is not None:
        if existing.username == body.username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="用户名已被占用"
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册"
        )

    user = _UserRow(
        username=body.username,
        email=body.email,
        password_hash=_hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _create_access_token(user.id)

    # # 为新用户创建缓存目录
    # safe_username = "".join(c for c in body.username if c.isalnum() or c in ("-", "_"))
    # user_cache_dir = os.path.join(WIKI_CACHE_DIR, safe_username)
    # os.makedirs(user_cache_dir, exist_ok=True)

    logger.info("New user registered: %s", user.username)
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return a JWT access token."""
    result = await db.execute(
        select(_UserRow).where(_UserRow.username == body.username)
    )
    user = result.scalars().first()
    if user is None or not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账户已停用"
        )

    token = _create_access_token(user.id)
    logger.info("User logged in: %s", user.username)
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: _UserRow = Depends(_get_current_user)):
    """Return the authenticated user's profile."""
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
