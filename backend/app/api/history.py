from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.conversation import Conversation, Message
router=APIRouter(prefix="/history",tags=["history"])
@router.post("")
async def list_history(db:AsyncSession=Depends(get_db),current_user=Depends(get_current_user)):
    r=await db.execute(select(Conversation).where(Conversation.user_id==current_user.id).order_by(Conversation.updated_at.desc()).limit(50));out=[]
    for c in r.scalars().all():
        m=await db.execute(select(Message).where(Message.conversation_id==c.id).order_by(Message.created_at.desc()).limit(2));msgs=list(m.scalars().all());preview=next((x.content for x in msgs if x.role=="assistant"),msgs[0].content if msgs else "No messages yet");out.append({"id":c.id,"title":c.title or "New chat","preview":preview[:120]})
    return {"saved":True,"history":out}
@router.post("/{conversation_id}")
async def get_history(conversation_id:int,db:AsyncSession=Depends(get_db),current_user=Depends(get_current_user)):
    r=await db.execute(select(Conversation).where(Conversation.id==conversation_id,Conversation.user_id==current_user.id));c=r.scalar_one_or_none()
    if not c: raise HTTPException(404,"Conversation not found")
    m=await db.execute(select(Message).where(Message.conversation_id==c.id).order_by(Message.created_at.asc()));return {"id":c.id,"title":c.title,"messages":[{"role":x.role,"content":x.content} for x in m.scalars().all()]}
