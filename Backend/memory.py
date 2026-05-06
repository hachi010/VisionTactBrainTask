from __future__ import annotations

import uuid
from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Conversation, Message


async def get_or_create_conversation(session: AsyncSession, conversation_id: str | None) -> str:
    if conversation_id:
        result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv:
            return conversation_id

    new_id = conversation_id or str(uuid.uuid4())
    session.add(Conversation(id=new_id))
    await session.commit()
    return new_id


async def load_messages(session: AsyncSession, conversation_id: str) -> list[BaseMessage]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id)
    )
    rows = result.scalars().all()

    messages: list[BaseMessage] = []
    for row in rows:
        if row.role == "user":
            messages.append(HumanMessage(content=row.content))
        elif row.role == "assistant":
            messages.append(AIMessage(content=row.content))
        elif row.role == "tool":
            messages.append(ToolMessage(content=row.content, tool_call_id="", name=row.tool_name or ""))
    return messages


async def save_message(
    session: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    tool_name: str | None = None,
) -> None:
    session.add(
        Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_name=tool_name,
        )
    )
    await session.commit()


async def list_conversations(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    convs = result.scalars().all()
    out = []
    for c in convs:
        # Get last message preview
        msg_result = await session.execute(
            select(Message)
            .where(Message.conversation_id == c.id)
            .order_by(Message.id.desc())
            .limit(1)
        )
        last_msg = msg_result.scalar_one_or_none()
        out.append({
            "id": c.id,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "preview": (last_msg.content[:80] + "...") if last_msg and len(last_msg.content) > 80 else (last_msg.content if last_msg else ""),
        })
    return out