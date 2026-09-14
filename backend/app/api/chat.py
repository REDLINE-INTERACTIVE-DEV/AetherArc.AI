from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import get_current_user, get_optional_user
from app.db.base import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.agents.manager import ManagerAI
from app.agents.base import AgentMessage

router = APIRouter(prefix="/chat", tags=["chat"])
manager = ManagerAI()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[int] = None
    force_agent: Optional[str] = None  # manager | research | coder | image
    # Opt-in: include short team_activity for "watch the team" UI. Default off.
    include_team_activity: bool = False


class TeamActivityItem(BaseModel):
    agent: str
    summary: str


class ChatResponse(BaseModel):
    conversation_id: Optional[int]
    type: str
    agent: str
    content: str  # user-facing final answer only
    team_activity: Optional[List[TeamActivityItem]] = None


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Chat with Manager (or a forced specialist).

    - Guests (no JWT): can chat freely. Nothing is written to the database.
      If they send conversation_id it is ignored.
    - Logged-in users: history is saved. conversation_id is accepted only when
      it belongs to the current user (ownership check).
    """
    history: List[AgentMessage] = []
    conversation: Optional[Conversation] = None

    # Guests never touch the DB — conversation_id from a guest is ignored
    if current_user is not None:
        if body.conversation_id is not None:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == body.conversation_id,
                    Conversation.user_id == current_user.id,  # ownership required
                )
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(404, "Conversation not found")
        else:
            conversation = Conversation(
                user_id=current_user.id,
                title=body.message[:80],
                agent_type=body.force_agent or "manager",
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        msgs = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(16)
        )
        for m in reversed(list(msgs.scalars().all())):
            role = m.role if m.role in ("user", "assistant") else "assistant"
            history.append(AgentMessage(role=role, content=m.content))

        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=body.message,
                agent_name=None,
            )
        )
        await db.commit()

    result = await manager.handle_user_message(
        message=body.message,
        history=history,
        force_agent=body.force_agent,
        include_team_activity=body.include_team_activity,
    )

    # Persist only for logged-in users
    if current_user is not None and conversation is not None:
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                agent_name=result.get("agent", "manager"),
                content=result["content"],
            )
        )
        # Optional short team activity stored as separate messages only if requested
        if body.include_team_activity and result.get("team_activity"):
            for item in result["team_activity"]:
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        agent_name=item["agent"],
                        content=item["summary"],
                    )
                )
        await db.commit()

    team_activity = None
    if result.get("team_activity"):
        team_activity = [
            TeamActivityItem(agent=i["agent"], summary=i["summary"])
            for i in result["team_activity"]
        ]

    return ChatResponse(
        conversation_id=conversation.id if conversation else None,
        type=result["type"],
        agent=result["agent"],
        content=result["content"],
        team_activity=team_activity,
    )


@router.get("/conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "agent_type": c.agent_type,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Conversation not found")

    msgs = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "agent_name": m.agent_name,
            "content": m.content,
            "created_at": m.created_at,
        }
        for m in msgs.scalars().all()
    ]
