from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission


CAPABILITIES: Dict[str, str] = {
    "files.read": "Read files",
    "files.write": "Create or modify files",
    "files.delete": "Delete files",
    "apps.run": "Run applications or commands",
    "software.install": "Install software",
    "web.browse": "Browse the web",
    "network.access": "Access external network services",
    "microphone.use": "Use the microphone",
    "camera.use": "Use the camera",
    "messages.send": "Send messages or emails",
    "accounts.access": "Access connected accounts and APIs",
    "computer.control": "Control the computer",
    "long_tasks.run": "Run long-running tasks",
}


class PermissionGate:
    """Central permission gate for every future Aether tool."""

    def __init__(self, db: AsyncSession, user_id: Optional[int]):
        self.db = db
        self.user_id = user_id

    async def modes(self) -> Dict[str, str]:
        result = {key: "ask" for key in CAPABILITIES}
        if self.user_id is None:
            return result
        rows = await self.db.execute(select(Permission).where(Permission.user_id == self.user_id))
        for row in rows.scalars().all():
            if row.capability in CAPABILITIES and row.mode in {"allow", "ask", "deny"}:
                result[row.capability] = row.mode
        return result

    async def check(self, capabilities: Iterable[str]) -> Dict[str, List[str]]:
        modes = await self.modes()
        allowed, needs_approval, denied = [], [], []
        for capability in capabilities:
            if capability not in CAPABILITIES:
                continue
            mode = modes.get(capability, "ask")
            if mode == "allow":
                allowed.append(capability)
            elif mode == "deny":
                denied.append(capability)
            else:
                needs_approval.append(capability)
        return {"allowed": allowed, "needs_approval": needs_approval, "denied": denied}

    async def set_mode(self, capability: str, mode: str) -> Permission:
        if capability not in CAPABILITIES:
            raise ValueError(f"Unknown capability: {capability}")
        if mode not in {"allow", "ask", "deny"}:
            raise ValueError("mode must be allow, ask, or deny")
        if self.user_id is None:
            raise ValueError("Login is required to save permissions")

        result = await self.db.execute(select(Permission).where(
            Permission.user_id == self.user_id,
            Permission.capability == capability,
        ))
        row = result.scalar_one_or_none()
        if row is None:
            row = Permission(user_id=self.user_id, capability=capability, mode=mode)
            self.db.add(row)
        else:
            row.mode = mode
        await self.db.commit()
        await self.db.refresh(row)
        return row
