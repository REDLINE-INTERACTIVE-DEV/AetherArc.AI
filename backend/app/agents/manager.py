from typing import Any, Dict, List, Optional
import asyncio
import json
import re

from app.agents.base import BaseAgent, AgentMessage
from app.agents.research import ResearchAI
from app.agents.coder import CoderAI
from app.agents.image import ImageAI


class ManagerAI(BaseAgent):
    name = "manager"
    description = "Project and team-management specialist used by Aether's central brain."

    system_prompt = """You are ManagerAI, Aether's project and team-management specialist.

Aether itself is the central intelligence. You are one specialist inside Aether, not Aether's
central brain and not the final authority.

Help Aether with project planning, task breakdown, implementation sequencing, progress
summaries and practical team organization. Keep responses natural, useful and decisive.
ImageAI only produces image prompts/concepts and does not generate real images yet."""

    def __init__(self):
        super().__init__()
        self.research = ResearchAI()
        self.coder = CoderAI()
        self.image = ImageAI()
        self.specialists = {
            "research": self.research, "researchai": self.research, "reason": self.research,
            "coder": self.coder, "coderai": self.coder, "code": self.coder,
            "image": self.image, "imageai": self.image, "video": self.image,
        }

    async def handle_user_message(
        self, message: str, history: Optional[List[AgentMessage]] = None,
        force_agent: Optional[str] = None, include_team_activity: bool = False,
    ) -> Dict[str, Any]:
        if force_agent:
            agent = self.specialists.get(force_agent.lower().strip())
            if not agent:
                return {"type": "error", "agent": "manager", "content": f"Unknown agent: {force_agent}"}
            resp = await agent.generate(message, history=history)
            return {"type": "direct", "agent": resp.agent, "content": resp.content}

        raw = await self.generate(
            "Decide whether this project-management request needs research, coding or image help. "
            "Return only JSON: {\"needs\":[],\"tasks\":{}}\n\nUser: " + message,
            temperature=0.2, max_tokens=300,
        )
        plan = self._parse_plan(raw.content)
        if not plan["needs"]:
            resp = await self.generate(message, history=history)
            return {"type": "direct", "agent": "manager", "content": resp.content}

        async def run_one(name: str) -> Dict[str, str]:
            agent = self.specialists[name]
            task = plan["tasks"].get(name) or message
            try:
                out = await agent.generate(task)
                return {"agent": out.agent, "content": out.content}
            except Exception as exc:
                return {"agent": name, "content": f"(error: {exc})"}

        results = await asyncio.gather(*[run_one(n) for n in plan["needs"]])
        reports = "\n\n".join(f"{r['agent'].upper()} report:\n{r['content']}" for r in results)
        final = await self.generate(
            f"User asked: {message}\n\nSpecialist reports:\n{reports}\n\n"
            "Give a concise project-management answer without exposing private routing.",
            history=history, temperature=0.5,
        )
        out = {"type": "report", "agent": "manager", "content": final.content}
        if include_team_activity:
            out["team_activity"] = [
                {"agent": r["agent"], "summary": r["content"][:400] + ("…" if len(r["content"]) > 400 else "")}
                for r in results
            ]
        return out

    def _parse_plan(self, raw: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(match.group(0)) if match else {}
            allowed = {"research", "coder", "image"}
            return {
                "needs": [n for n in (data.get("needs") or []) if n in allowed][:2],
                "tasks": data.get("tasks") if isinstance(data.get("tasks"), dict) else {},
            }
        except Exception:
            return {"needs": [], "tasks": {}}
