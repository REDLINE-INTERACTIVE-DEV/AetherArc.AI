from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import get_current_user, get_optional_user
from app.db.base import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.agents.base import AgentMessage
from app.core.brain import AetherBrain

router = APIRouter(prefix="/chat", tags=["chat"])
brain = AetherBrain()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[int] = None
    force_agent: Optional[str] = None  # aether | manager | research | coder | image
    include_team_activity: bool = False


class TeamActivityItem(BaseModel):
    agent: str
    summary: str


class ChatResponse(BaseModel):
    conversation_id: Optional[int]
    type: str
    agent: str
    content: str
    team_activity: Optional[List[TeamActivityItem]] = None
    permission_required: Optional[List[str]] = None


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    history: List[AgentMessage] = []
    conversation: Optional[Conversation] = None

    if current_user is not None:
        if body.conversation_id is not None:
            result = await db.execute(select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.user_id == current_user.id,
            ))
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(404, "Conversation not found")
        else:
            conversation = Conversation(
                user_id=current_user.id, title=body.message[:80],
                agent_type=body.force_agent or "aether",
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        msgs = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc()).limit(16)
        )
        for m in reversed(list(msgs.scalars().all())):
            role = m.role if m.role in ("user", "assistant") else "assistant"
            history.append(AgentMessage(role=role, content=m.content))

        db.add(Message(conversation_id=conversation.id, role="user", content=body.message))
        await db.commit()

    result = await brain.handle_user_message(
        message=body.message,
        history=history,
        force_agent=body.force_agent,
        include_team_activity=body.include_team_activity,
        db=db,
        user_id=current_user.id if current_user is not None else None,
    )

    # Permission prompts are state-free: after the user changes a permission, the same
    # request can be sent again and the gateway will re-check it before any tool runs.
    if current_user is not None and conversation is not None and result.get("type") not in {
        "permission_required", "permission_denied"
    }:
        db.add(Message(
            conversation_id=conversation.id, role="assistant",
            agent_name=result.get("agent", "aether"), content=result["content"],
        ))
        if body.include_team_activity and result.get("team_activity"):
            for item in result["team_activity"]:
                db.add(Message(
                    conversation_id=conversation.id, role="assistant",
                    agent_name=item["agent"], content=item["summary"],
                ))
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
        permission_required=result.get("permission_required"),
    )


@router.get("/conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Conversation).where(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()))
    convs = result.scalars().all()
    return [{
        "id": c.id, "title": c.title, "agent_type": c.agent_type,
        "created_at": c.created_at, "updated_at": c.updated_at,
    } for c in convs]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == current_user.id
    ))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Conversation not found")

    msgs = await db.execute(select(Message).where(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at))
    return [{
        "id": m.id, "role": m.role, "agent_name": m.agent_name,
        "content": m.content, "created_at": m.created_at,
    } for m in msgs.scalars().all()]
