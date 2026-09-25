from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    from app.models import user, conversation, access
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            columns = await conn.execute(text("PRAGMA table_info(users)"))
            names = {row[1] for row in columns.fetchall()}
            if "password_hash" not in names:
                await conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"))
