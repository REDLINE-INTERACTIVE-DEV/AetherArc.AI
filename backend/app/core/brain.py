from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agents.base import AgentMessage
from app.core.native_brain import AetherNativeBrain


class AetherBrain:
    """Aether's central front door backed by Aether's native cognitive core.

    The production chat path deliberately does not call BaseAgent or any external
    model provider. Specialist/provider integrations are kept outside this brain
    until Aether-native versions exist.
    """

    name = "aether"
    description = "Aether's native provider-free cognitive brain."

    def __init__(self) -> None:
        self.native = AetherNativeBrain()

    async def handle_user_message(
        self,
        message: str,
        history: Optional[List[AgentMessage]] = None,
        force_agent: Optional[str] = None,
        include_team_activity: bool = False,
        db: Any = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if force_agent and force_agent.lower().strip() not in ("aether", "brain", "aetherbrain"):
            return {
                "type": "error",
                "agent": "aether",
                "content": (
                    "Aether's native brain is the active intelligence. "
                    "External-model specialist agents are intentionally not used as Aether's brain."
                ),
                "brain": "aether-native",
                "external_model_used": False,
            }

        result = await self.native.respond(message, history=history)
        output: Dict[str, Any] = {
            "type": "direct",
            "agent": "aether",
            "content": result["content"],
            "brain": "aether-native",
            "external_model_used": False,
        }
        if include_team_activity:
            output["team_activity"] = []
        return output
