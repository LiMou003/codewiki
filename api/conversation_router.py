"""
Conversation router for CodeWiki.

Provides six endpoints for managing conversations and their messages:
    GET    /api/conversations                  — list conversations for a repo
    POST   /api/conversations                  — create a new conversation
    DELETE /api/conversations/{id}             — delete a conversation
    GET    /api/conversations/{id}/messages    — get messages of a conversation
    POST   /api/conversations/{id}/messages    — create a message
    DELETE /api/conversations/{cid}/messages/{mid} — delete a message

All endpoints require a valid JWT token (Bearer).
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth_router import get_current_user
from api.database import get_db
from api.database.models import (
    Conversation,
    ConversationMessage,
    MessageFeedback,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ConversationOut(BaseModel):
    id: str
    userId: str
    repoOwner: str
    repoName: str
    repoType: str
    title: Optional[str]
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class CreateConversationRequest(BaseModel):
    repoOwner: str = Field(..., description="仓库所有者")
    repoName: str = Field(..., description="仓库名称")
    repoType: Optional[str] = Field("github", description="仓库类型")
    title: Optional[str] = Field(None, description="对话标题")


class MessageOut(BaseModel):
    id: str
    conversationId: str
    role: str
    content: str
    tokenCount: Optional[int]
    feedbackStatus: Optional[str] = None
    messageType: str = "normal"
    createdAt: datetime

    class Config:
        from_attributes = True


class CreateMessageRequest(BaseModel):
    role: str = Field(..., description="消息角色：user 或 assistant")
    content: str = Field(..., description="消息内容")
    tokenCount: Optional[int] = Field(None, description="Token 数量")
    messageType: Optional[str] = Field("normal", description="消息类型：normal 或 deep_research")


class CreateFeedbackRequest(BaseModel):
    feedbackType: str = Field(..., description="反馈类型：liked 或 disliked")
    comment: Optional[str] = Field(None, description="点踩时的文字反馈")


# ---------------------------------------------------------------------------
# Helper: convert ORM model → Pydantic output
# ---------------------------------------------------------------------------

def _conversation_to_out(conv: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        userId=conv.user_id,
        repoOwner=conv.repo_owner,
        repoName=conv.repo_name,
        repoType=conv.repo_type,
        title=conv.title,
        createdAt=conv.created_at,
        updatedAt=conv.updated_at,
    )


def _message_to_out(msg: ConversationMessage) -> MessageOut:
    return MessageOut(
        id=msg.id,
        conversationId=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        tokenCount=msg.token_count,
        feedbackStatus=msg.feedback_status,
        messageType=msg.message_type,
        createdAt=msg.created_at,
    )


# ---------------------------------------------------------------------------
# 1. GET /api/conversations — 获取历史对话列表
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[ConversationOut])
async def list_conversations(
    repo_owner: str = Query(..., alias="repo_owner", description="仓库所有者"),
    repo_name: str = Query(..., alias="repo_name", description="仓库名称"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户在指定仓库下的所有历史对话（按更新时间倒序）。"""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.repo_owner == repo_owner,
            Conversation.repo_name == repo_name,
        )
        .order_by(desc(Conversation.updated_at))
    )
    conversations = result.scalars().all()
    return [_conversation_to_out(c) for c in conversations]


# ---------------------------------------------------------------------------
# 2. POST /api/conversations — 新增对话
# ---------------------------------------------------------------------------

@router.post("/", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为当前用户在指定仓库下创建一个新的对话。"""
    conv = Conversation(
        id=str(uuid4()),
        user_id=current_user.id,
        repo_owner=body.repoOwner,
        repo_name=body.repoName,
        repo_type=body.repoType or "github",
        title=body.title,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    logger.info("Created conversation %s for user %s repo %s/%s",
                conv.id, current_user.id, body.repoOwner, body.repoName)
    return _conversation_to_out(conv)


# ---------------------------------------------------------------------------
# 3. DELETE /api/conversations/{conversation_id} — 删除对话
# ---------------------------------------------------------------------------

@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定对话及其所有消息（级联删除）。"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )
    await db.delete(conv)
    await db.commit()
    logger.info("Deleted conversation %s for user %s", conversation_id, current_user.id)
    return None


# ---------------------------------------------------------------------------
# 4. GET /api/conversations/{conversation_id}/messages — 获取对话内容
# ---------------------------------------------------------------------------

@router.get("/{conversation_id}/messages", response_model=List[MessageOut])
async def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定对话的所有消息（按创建时间正序）。"""
    # 验证对话归属
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    )
    messages = result.scalars().all()
    return [_message_to_out(m) for m in messages]


# ---------------------------------------------------------------------------
# 5. POST /api/conversations/{conversation_id}/messages — 新增对话内容
# ---------------------------------------------------------------------------

@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201)
async def create_conversation_message(
    conversation_id: str,
    body: CreateMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """在指定对话中新增一条消息。"""
    if body.role not in ("user", "assistant"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色必须是 'user' 或 'assistant'",
        )

    # 验证对话归属
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    msg = ConversationMessage(
        id=str(uuid4()),
        conversation_id=conversation_id,
        role=body.role,
        content=body.content,
        token_count=body.tokenCount,
        message_type=body.messageType or "normal",
    )
    db.add(msg)

    # 更新对话的 updated_at 字段
    conv.updated_at = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

    await db.commit()
    await db.refresh(msg)
    logger.info("Created message %s in conversation %s", msg.id, conversation_id)
    return _message_to_out(msg)


# ---------------------------------------------------------------------------
# 6. DELETE /api/conversations/{conversation_id}/messages/{message_id} — 删除对话内容
# ---------------------------------------------------------------------------

@router.delete("/{conversation_id}/messages/{message_id}", status_code=204)
async def delete_conversation_message(
    conversation_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定对话中的一条消息。"""
    # 验证对话归属
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    result = await db.execute(
        select(ConversationMessage).where(
            ConversationMessage.id == message_id,
            ConversationMessage.conversation_id == conversation_id,
        )
    )
    msg = result.scalars().first()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在",
        )
    await db.delete(msg)
    await db.commit()
    logger.info("Deleted message %s from conversation %s", message_id, conversation_id)
    return None


# ---------------------------------------------------------------------------
# 6.5 PATCH /api/conversations/{cid}/messages/{mid} — 更新对话内容
# ---------------------------------------------------------------------------

class UpdateMessageRequest(BaseModel):
    content: Optional[str] = Field(None, description="消息内容")
    tokenCount: Optional[int] = Field(None, description="Token 数量")
    messageType: Optional[str] = Field(None, description="消息类型：normal 或 deep_research")


@router.patch("/{conversation_id}/messages/{message_id}", response_model=MessageOut)
async def update_conversation_message(
    conversation_id: str,
    message_id: str,
    body: UpdateMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新指定对话中的一条消息。"""
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    result = await db.execute(
        select(ConversationMessage).where(
            ConversationMessage.id == message_id,
            ConversationMessage.conversation_id == conversation_id,
        )
    )
    msg = result.scalars().first()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在",
        )

    if body.content is not None:
        msg.content = body.content
    if body.tokenCount is not None:
        msg.token_count = body.tokenCount
    if body.messageType is not None:
        msg.message_type = body.messageType

    conv.updated_at = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

    await db.commit()
    await db.refresh(msg)
    logger.info("Updated message %s in conversation %s", message_id, conversation_id)
    return _message_to_out(msg)


# ---------------------------------------------------------------------------
# 7. POST /api/conversations/{cid}/messages/{mid}/feedback — 提交/更新消息反馈
# ---------------------------------------------------------------------------

class FeedbackOut(BaseModel):
    id: str
    messageId: str
    userId: str
    feedbackType: str
    comment: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True


@router.post(
    "/{conversation_id}/messages/{message_id}/feedback",
    response_model=FeedbackOut,
    status_code=201,
)
async def submit_message_feedback(
    conversation_id: str,
    message_id: str,
    body: CreateFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为指定消息提交反馈（点赞或点踩），每条消息仅可反馈一次。"""
    if body.feedbackType not in ("liked", "disliked"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="反馈类型必须是 'liked' 或 'disliked'",
        )

    # 验证对话归属
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    # 查询消息
    msg_result = await db.execute(
        select(ConversationMessage).where(
            ConversationMessage.id == message_id,
            ConversationMessage.conversation_id == conversation_id,
        )
    )
    msg = msg_result.scalars().first()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在",
        )

    # 检查是否已经反馈过
    if msg.feedback_status is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该消息已经反馈过，无法重复提交",
        )

    # 更新消息的反馈状态
    msg.feedback_status = body.feedbackType

    # 创建反馈记录
    feedback = MessageFeedback(
        id=str(uuid4()),
        message_id=message_id,
        user_id=current_user.id,
        feedback_type=body.feedbackType,
        comment=body.comment,
    )
    db.add(feedback)

    await db.commit()
    await db.refresh(feedback)

    logger.info(
        "Feedback %s (%s) submitted for message %s by user %s",
        feedback.id, body.feedbackType, message_id, current_user.id,
    )

    return FeedbackOut(
        id=feedback.id,
        messageId=feedback.message_id,
        userId=feedback.user_id,
        feedbackType=feedback.feedback_type,
        comment=feedback.comment,
        createdAt=feedback.created_at,
    )
