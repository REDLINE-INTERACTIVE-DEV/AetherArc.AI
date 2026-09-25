from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import GuestAccess, GUEST_MESSAGE_LIMIT, hash_guest_token


async def consume_guest_message(db: AsyncSession, token: str) -> int:
    token_hash = hash_guest_token(token)
    result = await db.execute(select(GuestAccess).where(GuestAccess.token_hash == token_hash))
    guest = result.scalar_one_or_none()
    if guest is None:
        raise HTTPException(status_code=401, detail="Invalid guest session")
    if guest.messages_used >= guest.max_messages:
        raise HTTPException(
            status_code=429,
            detail="Guest message limit reached. Log in to continue using Aether.",
        )

    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(GuestAccess)
        .where(
            GuestAccess.token_hash == token_hash,
            GuestAccess.messages_used < GuestAccess.max_messages,
        )
        .values(messages_used=GuestAccess.messages_used + 1, last_used_at=now)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=429,
            detail="Guest message limit reached. Log in to continue using Aether.",
        )

    await db.commit()
    await db.refresh(guest)
    return max(0, guest.max_messages - guest.messages_used)


async def create_guest_session(db: AsyncSession) -> tuple[str, int]:
    from app.models.access import create_guest_token

    token = create_guest_token()
    db.add(
        GuestAccess(
            token_hash=hash_guest_token(token),
            messages_used=0,
            max_messages=GUEST_MESSAGE_LIMIT,
        )
    )
    await db.commit()
    return token, GUEST_MESSAGE_LIMIT
