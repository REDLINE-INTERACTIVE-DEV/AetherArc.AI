from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.base import get_db
from app.models.user import User
from app.models.access import GuestAccess, hash_guest_token, verify_user_api_key

security = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def create_access_token(subject: str | int, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": str(subject), "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except (JWTError, TypeError):
        return None


async def resolve_user_from_token(token: str, db: AsyncSession) -> User | None:
    user_id: str | None = None

    if token.startswith("aeth_u_"):
        parsed_id = verify_user_api_key(token, settings.SECRET_KEY)
        if parsed_id is None:
            return None
        user_id = str(parsed_id)
    else:
        user_id = verify_token(token)

    if user_id is None or not user_id.isdigit():
        return None

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in with Google or GitHub.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await resolve_user_from_token(credentials.credentials, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired Aether credential")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None
    return await resolve_user_from_token(credentials.credentials, db)


async def get_request_identity(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if credentials is None:
        return None, None

    token = credentials.credentials
    user = await resolve_user_from_token(token, db)
    if user is not None:
        return user, None

    if token.startswith("aeth_g_"):
        result = await db.execute(
            select(GuestAccess).where(GuestAccess.token_hash == hash_guest_token(token))
        )
        guest = result.scalar_one_or_none()
        if guest is not None:
            return None, token

    raise HTTPException(status_code=401, detail="Invalid or expired Aether credential")
