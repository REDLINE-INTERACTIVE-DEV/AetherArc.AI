from datetime import datetime, timezone
import base64
import hashlib
import hmac
import secrets

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

GUEST_MESSAGE_LIMIT = 10
USER_KEY_PREFIX = "aeth_u_"
GUEST_KEY_PREFIX = "aeth_g_"


class GuestAccess(Base):
    __tablename__ = "guest_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    messages_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_messages: Mapped[int] = mapped_column(Integer, default=GUEST_MESSAGE_LIMIT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * ((-len(value)) % 4))


def _user_signature(user_id: int, secret_key: str) -> str:
    payload = f"user:{user_id}".encode()
    return _b64(hmac.new(secret_key.encode(), payload, hashlib.sha256).digest())


def create_user_api_key(user_id: int, secret_key: str) -> str:
    encoded_id = _b64(str(user_id).encode())
    signature = _user_signature(user_id, secret_key)
    return f"{USER_KEY_PREFIX}{encoded_id}.{signature}"


def verify_user_api_key(api_key: str, secret_key: str) -> int | None:
    if not api_key.startswith(USER_KEY_PREFIX):
        return None
    try:
        payload = api_key[len(USER_KEY_PREFIX):]
        encoded_id, signature = payload.split(".", 1)
        user_id = int(_unb64(encoded_id).decode())
    except (ValueError, UnicodeDecodeError, TypeError):
        return None
    expected = _user_signature(user_id, secret_key)
    if hmac.compare_digest(signature, expected):
        return user_id
    return None


def create_guest_token() -> str:
    return f"{GUEST_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_guest_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
