from typing import Any, Dict, List, Optional
import asyncio
import json
import re

from app.agents.base import BaseAgent, AgentResponse, AgentMessage
from app.agents.research import ResearchAI
from app.agents.coder import CoderAI
from app.agents.image import ImageAI


class ManagerAI(BaseAgent):
    name = "manager"
    description = "The boss. Talks to the user, assigns parallel tasks to specialists, delivers final reports."
    system_prompt = """You are ManagerAI, the clear boss of the AetherArc AI team.

Your team:
- ResearchAI → research, summarization, fact-finding
- CoderAI → coding, debugging, architecture
- ImageAI → image prompts and visual concepts only (does not generate real images yet)

Your job:
1. Talk directly and helpfully with the user.
2. Decide which specialist(s) are needed.
3. When useful, assign tasks to multiple specialists IN PARALLEL.
4. Collect their results and synthesize one clear final report for the user.
5. Always credit which specialist contributed when you use them.
6. The user can also talk directly to any specialist.

Be professional, decisive, and transparent.
Never invent that an image was generated — ImageAI only produces prompts/concepts."""

    def __init__(self):
        super().__init__()
        self.research = ResearchAI()
        self.coder = CoderAI()
        self.image = ImageAI()
        self.specialists = {
            "research": self.research,
            "researchai": self.research,
            "reason": self.research,
            "coder": self.coder,
            "coderai": self.coder,
            "code": self.coder,
            "image": self.image,
            "imageai": self.image,
            "video": self.image,
        }

    async def handle_user_message(
        self,
        message: str,
        history: Optional[List[AgentMessage]] = None,
        force_agent: Optional[str] = None,
        include_team_activity: bool = False,
    ) -> Dict[str, Any]:
        """
        Returns a dict with at least:
          - type: "direct" | "report" | "error"
          - agent: which agent produced the user-facing content
          - content: the user-facing final answer (ALWAYS present)

        Optionally (only when include_team_activity=True):
          - team_activity: list of {agent, summary} for UI "watch the team" feature
        Internal routing prompts are never returned.
        """
        if force_agent:
            key = force_agent.lower().strip()
            if key in ("manager", "managerai"):
                resp = await self.generate(message, history=history)
                return {"type": "direct", "agent": "manager", "content": resp.content}
            agent = self.specialists.get(key)
            if not agent:
                return {"type": "error", "agent": "manager", "content": f"Unknown agent: {force_agent}"}
            resp = await agent.generate(message, history=history)
            return {"type": "direct", "agent": agent.name, "content": resp.content}

        # Internal router — output never sent to the client
        router_prompt = (
            "You are the internal router for ManagerAI. The user never sees this.\n"
            "Decide which specialists (if any) are needed for the user message.\n"
            "Reply with ONLY compact JSON, no markdown:\n"
            '{"needs":["research","coder"],"tasks":{"research":"specific sub-question","coder":"specific sub-question"}}\n'
            "needs can contain 0, 1 or 2 of: research, coder, image.\n"
            "Most simple greetings or easy questions need []."
        )
        try:
            raw = await self.generate(
                f"{router_prompt}\n\nUser message:\n{message}",
                temperature=0.2,
                max_tokens=300,
            )
            plan = self._parse_plan(raw.content)
        except Exception:
            plan = {"needs": [], "tasks": {}}

        if not plan["needs"]:
            resp = await self.generate(message, history=history)
            return {"type": "direct", "agent": "manager", "content": resp.content}

        async def run_one(name: str) -> Dict[str, str]:
            agent = self.specialists.get(name)
            if not agent:
                return {"agent": name, "content": f"(unknown specialist {name})"}
            task = plan["tasks"].get(name) or message
            try:
                out = await agent.generate(task, history=None)
                return {"agent": agent.name, "content": out.content}
            except Exception as e:
                return {"agent": name, "content": f"(error: {e})"}

        results = await asyncio.gather(*[run_one(n) for n in plan["needs"]])

        reports_text = "\n\n".join(
            f"{r['agent'].upper()} report:\n{r['content']}" for r in results
        )
        briefing = (
            f"User asked: {message}\n\n"
            f"Your specialists returned:\n{reports_text}\n\n"
            "Write the final clear answer for the user. Credit which teammate(s) you used. "
            "Do not dump raw internal reports — synthesize a clean response."
        )
        final = await self.generate(briefing, history=history, temperature=0.5)

        out: Dict[str, Any] = {
            "type": "report",
            "agent": "manager",
            "content": final.content,  # user-facing only
        }
        if include_team_activity:
            # Short, UI-safe summaries — not full internal dumps
            out["team_activity"] = [
                {
                    "agent": r["agent"],
                    "summary": (r["content"][:400] + "…") if len(r["content"]) > 400 else r["content"],
                }
                for r in results
            ]
        return out

    def _parse_plan(self, raw: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                return {"needs": [], "tasks": {}}
            data = json.loads(match.group(0))
            allowed = {"research", "coder", "image"}
            needs = [n for n in (data.get("needs") or []) if n in allowed][:2]
            tasks = data.get("tasks") if isinstance(data.get("tasks"), dict) else {}
            return {"needs": needs, "tasks": tasks}
        except Exception:
            return {"needs": [], "tasks": {}}
