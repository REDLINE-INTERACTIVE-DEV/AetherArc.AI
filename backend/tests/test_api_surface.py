import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.base import Base
from app.api.auth import GuestResponse, TokenResponse
from app.api.chat import ChatResponse

assert GuestResponse.model_fields["messages_remaining"].annotation is int
assert TokenResponse.model_fields["aether_api_key"].annotation is str
assert ChatResponse.model_fields["guest_messages_remaining"].annotation == int | None


async def main():
    assert "guest_access" in Base.metadata.tables
    print("API_SURFACE_TESTS_OK")


asyncio.run(main())
