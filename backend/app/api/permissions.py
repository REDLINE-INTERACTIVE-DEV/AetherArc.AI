from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import CAPABILITIES, PermissionGate
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User

router = APIRouter(prefix="/permissions", tags=["permissions"])


class PermissionUpdate(BaseModel):
    mode: str


@router.get("")
async def list_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gate = PermissionGate(db, current_user.id)
    modes = await gate.modes()
    return {
        "capabilities": [
            {"id": key, "label": label, "mode": modes[key]}
            for key, label in CAPABILITIES.items()
        ]
    }


@router.put("/{capability}")
async def update_permission(
    capability: str,
    body: PermissionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gate = PermissionGate(db, current_user.id)
    try:
        row = await gate.set_mode(capability, body.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": row.capability, "mode": row.mode}
