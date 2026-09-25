from __future__ import annotations
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from app.agents.base import AgentMessage
from app.core.native_brain import AetherNativeBrain

class AetherBrain:
    """Aether's front door and owner of isolated native cognitive sessions."""
    name = "aether"
    description = "Aether's native provider-free cognitive brain."

    def __init__(self, max_sessions: int = 256) -> None:
        self._sessions: "OrderedDict[str, AetherNativeBrain]" = OrderedDict()
        self.max_sessions = max_sessions

    def _key(self, user_id: Optional[int], conversation_id: Optional[int], session_id: Optional[str]) -> str:
        if user_id is not None: return f"user:{user_id}:conversation:{conversation_id or 'default'}"
        if session_id: return "guest:" + session_id.strip()[:128]
        return "guest:ephemeral"

    def _get(self, key: str) -> AetherNativeBrain:
        brain = self._sessions.get(key)
        if brain is None: brain = AetherNativeBrain(); self._sessions[key] = brain
        else: self._sessions.move_to_end(key)
        while len(self._sessions) > self.max_sessions: self._sessions.popitem(last=False)
        return brain

    async def handle_user_message(self, message: str, history: Optional[List[AgentMessage]] = None, force_agent: Optional[str] = None,
                                  include_team_activity: bool = False, db: Any = None, user_id: Optional[int] = None,
                                  conversation_id: Optional[int] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        if force_agent and force_agent.lower().strip() not in ("aether", "brain", "aetherbrain"):
            return {"type":"error","agent":"aether","content":"Aether's native brain is the active intelligence. External-model specialist agents are not used as Aether's brain.","brain":"aether-native","external_model_used":False}
        result = await self._get(self._key(user_id, conversation_id, session_id)).respond(message, history)
        output = {"type":"direct","agent":"aether","content":result["content"],"brain":"aether-native","external_model_used":False,
                  "intent":result["intent"],"confidence":result["confidence"],"topic":result.get("topic"),"tone":result.get("tone"),
                  "emotion":result.get("emotion"),"cognitive_state":result.get("cognitive_state")}
        if include_team_activity: output["team_activity"] = []
        return output
