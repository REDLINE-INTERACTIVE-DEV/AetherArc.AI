from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel

from app.core.config import settings


class AgentMessage(BaseModel):
    role: str
    content: str


class AgentResponse(BaseModel):
    content: str
    agent: str
    raw: Optional[Dict[str, Any]] = None


class BaseAgent:
    name: str = "base"
    description: str = ""
    system_prompt: str = "You are a helpful AI assistant."

    def __init__(self):
        self.model = settings.AI_MODEL

    async def generate(
        self,
        user_message: str,
        history: Optional[List[AgentMessage]] = None,
        temperature: float = 0.5,
        max_tokens: int = 1200,
    ) -> AgentResponse:
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            for h in history[-12:]:
                messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": user_message})

        if not settings.AI_API_KEY:
            return AgentResponse(
                content="[Backend error] AI_API_KEY is not set on the server. Put your key in backend/.env",
                agent=self.name,
            )

        headers = {
            "Authorization": f"Bearer {settings.AI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(
                f"{settings.AI_BASE_URL.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            if r.status_code >= 400:
                return AgentResponse(
                    content=f"[AI provider error {r.status_code}] {r.text[:400]}",
                    agent=self.name,
                )
            data = r.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return AgentResponse(content=text or "(empty response)", agent=self.name, raw=data)
