from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.security import get_request_identity
from app.core.access import consume_guest_message
from app.db.base import get_db
from app.models.conversation import Conversation, Message
from app.agents.base import AgentMessage
from app.core.brain import AetherBrain

router = APIRouter(prefix="/chat", tags=["chat"])
brain = AetherBrain()

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[int] = None
    session_id: Optional[str] = Field(default=None, min_length=8, max_length=128)
    force_agent: Optional[str] = None
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
    brain: Optional[str] = None
    external_model_used: bool = False
    guest_messages_remaining: Optional[int] = None

class ConversationPreview(BaseModel):
    id: int
    title: str
    updated_at: datetime

class ConversationListResponse(BaseModel):
    conversations: List[ConversationPreview]

class StoredMessage(BaseModel):
    role: str
    content: str
    agent_name: Optional[str] = None

class ConversationResponse(BaseModel):
    id: int
    title: str
    messages: List[StoredMessage]

@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(limit: int = Query(default=2, ge=1, le=2), db: AsyncSession = Depends(get_db), identity=Depends(get_request_identity)):
    current_user, guest_token = identity
    if current_user is None:
        return ConversationListResponse(conversations=[])
    result = await db.execute(select(Conversation).where(Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc()).limit(limit))
    return ConversationListResponse(conversations=[ConversationPreview(id=c.id, title=c.title, updated_at=c.updated_at) for c in result.scalars().all()])

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int, db: AsyncSession = Depends(get_db), identity=Depends(get_request_identity)):
    current_user, guest_token = identity
    if current_user is None:
        raise HTTPException(401, "Sign in to view saved conversations.")
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id))
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    msgs = await db.execute(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc()).limit(100))
    return ConversationResponse(id=conversation.id, title=conversation.title, messages=[StoredMessage(role=m.role, content=m.content, agent_name=m.agent_name) for m in msgs.scalars().all()])

@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db), identity=Depends(get_request_identity)):
    current_user, guest_token = identity
    if current_user is None and guest_token is None:
        raise HTTPException(401, "Aether needs a logged-in account or a guest session.")
    guest_remaining = None
    if guest_token is not None:
        guest_remaining = await consume_guest_message(db, guest_token)
    history: List[AgentMessage] = []
    conversation: Optional[Conversation] = None
    if current_user is not None:
        if body.conversation_id is not None:
            result = await db.execute(select(Conversation).where(Conversation.id == body.conversation_id, Conversation.user_id == current_user.id))
            conversation = result.scalar_one_or_none()
            if not conversation: raise HTTPException(404, "Conversation not found")
        else:
            conversation = Conversation(user_id=current_user.id, title=body.message[:80], agent_type="aether")
            db.add(conversation); await db.commit(); await db.refresh(conversation)
        msgs = await db.execute(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc()).limit(16))
        for m in reversed(list(msgs.scalars().all())): history.append(AgentMessage(role=m.role if m.role in ("user","assistant") else "assistant", content=m.content))
        db.add(Message(conversation_id=conversation.id, role="user", content=body.message))
        conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()
    result = await brain.handle_user_message(message=body.message, history=history, force_agent=body.force_agent, include_team_activity=body.include_team_activity, user_id=current_user.id if current_user is not None else None, conversation_id=conversation.id if conversation is not None else None, session_id=body.session_id)
    if current_user is not None and conversation is not None:
        db.add(Message(conversation_id=conversation.id, role="assistant", agent_name=result.get("agent","aether"), content=result["content"]))
        conversation.updated_at = datetime.now(timezone.utc)
        if body.include_team_activity and result.get("team_activity"):
            for item in result["team_activity"]: db.add(Message(conversation_id=conversation.id, role="assistant", agent_name=item["agent"], content=item["summary"]))
        await db.commit()
    return ChatResponse(conversation_id=conversation.id if conversation else None, type=result["type"], agent=result["agent"], content=str(result["content"]), team_activity=[TeamActivityItem(agent=i["agent"],summary=i["summary"]) for i in result["team_activity"]] if result.get("team_activity") else None, permission_required=result.get("permission_required"), brain=result.get("brain"), external_model_used=bool(result.get("external_model_used",False)), guest_messages_remaining=guest_remaining)
