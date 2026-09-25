import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.base import Base
from app.models.user import User
from app.core.access import create_guest_session, consume_guest_message
from app.models.access import create_user_api_key, verify_user_api_key
from fastapi import HTTPException

engine = create_async_engine("sqlite+aiosqlite:///:memory:")
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        user = User(email="test@example.com", provider="google", provider_id="test-user")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        key = create_user_api_key(user.id, "test-secret")
        assert verify_user_api_key(key, "test-secret") == user.id
        assert verify_user_api_key(key, "wrong-secret") is None

        token, limit = await create_guest_session(db)
        assert limit == 10
        for expected in range(9, -1, -1):
            assert await consume_guest_message(db, token) == expected

        try:
            await consume_guest_message(db, token)
            raise AssertionError("Expected guest quota rejection")
        except HTTPException as exc:
            assert exc.status_code == 429

    await engine.dispose()
    print("ACCESS_TESTS_OK")


asyncio.run(main())
