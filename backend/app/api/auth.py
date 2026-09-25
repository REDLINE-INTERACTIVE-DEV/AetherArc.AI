from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import httpx

from app.core.config import settings
from app.core.security import create_access_token, get_current_user
from app.core.access import create_guest_session
from app.models.user import User, hash_password, verify_password
from app.models.access import create_user_api_key
from app.db.base import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    aether_api_key: str

class GuestResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    mode: str = "guest"
    messages_remaining: int
    max_messages: int

class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)

class OAuthCodeExchange(BaseModel):
    provider: str = Field(pattern="^(google|github)$")
    code: str = Field(min_length=10, max_length=2048)

def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "provider": user.provider,
    }

def _validate_email(value: str) -> str:
    value = value.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@") or "." not in value.rsplit("@", 1)[-1]:
        raise HTTPException(400, "Enter a valid email address.")
    return value

@router.post("/register", response_model=TokenResponse)
async def register(body: Credentials, db: AsyncSession = Depends(get_db)):
    email = _validate_email(body.email)
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    user = User(
        email=email,
        name=email.split("@", 1)[0],
        provider="email",
        provider_id=email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=_user_payload(user),
        aether_api_key=create_user_api_key(user.id, settings.SECRET_KEY),
    )

@router.post("/login", response_model=TokenResponse)
async def login(body: Credentials, db: AsyncSession = Depends(get_db)):
    email = _validate_email(body.email)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(403, "This account is inactive.")
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=_user_payload(user),
        aether_api_key=create_user_api_key(user.id, settings.SECRET_KEY),
    )

@router.get("/google/login")
async def google_login():
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google login is not configured on the Aether server.")
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return {"login_url": "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}"
        "&response_type=code&scope=openid%20email%20profile&access_type=offline&prompt=select_account"}

@router.get("/github/login")
async def github_login():
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(503, "GitHub login is not configured on the Aether server.")
    redirect_uri = settings.GITHUB_REDIRECT_URI
    return {"login_url": "https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}&redirect_uri={redirect_uri}&scope=user:email"}

@router.post("/exchange", response_model=TokenResponse)
async def exchange_oauth(body: OAuthCodeExchange, db: AsyncSession = Depends(get_db)):
    if body.provider == "google":
        identity = await _verify_google(body.code)
    else:
        identity = await _verify_github(body.code)
    result = await db.execute(select(User).where(
        User.provider == identity["provider"],
        User.provider_id == identity["provider_id"],
    ))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(User).where(User.email == identity["email"]))
        user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=identity["email"], name=identity.get("name"),
            avatar_url=identity.get("avatar_url"),
            provider=identity["provider"], provider_id=identity["provider_id"],
        )
        db.add(user)
    else:
        user.name = identity.get("name") or user.name
        user.avatar_url = identity.get("avatar_url") or user.avatar_url
        user.email = identity["email"]
        user.provider = identity["provider"]
        user.provider_id = identity["provider_id"]
    await db.commit()
    await db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=_user_payload(user),
        aether_api_key=create_user_api_key(user.id, settings.SECRET_KEY),
    )

async def _verify_google(code: str) -> dict:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google login is not fully configured on the Aether server.")
    async with httpx.AsyncClient(timeout=20) as client:
        token = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token.status_code >= 400:
            raise HTTPException(401, "Google authorization failed.")
        access = token.json().get("access_token")
        if not access:
            raise HTTPException(401, "Google did not return an access token.")
        info = await client.get("https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access}"})
        if info.status_code >= 400:
            raise HTTPException(401, "Could not read Google account.")
        data = info.json()
    return {"provider":"google","provider_id":str(data["sub"]),
            "email":data["email"],"name":data.get("name"),"avatar_url":data.get("picture")}

async def _verify_github(code: str) -> dict:
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(503, "GitHub login is not fully configured on the Aether server.")
    async with httpx.AsyncClient(timeout=20) as client:
        token = await client.post("https://github.com/login/oauth/access_token",
            headers={"Accept":"application/json"},
            data={"client_id":settings.GITHUB_CLIENT_ID,"client_secret":settings.GITHUB_CLIENT_SECRET,
                  "code":code,"redirect_uri":settings.GITHUB_REDIRECT_URI})
        if token.status_code >= 400 or not token.json().get("access_token"):
            raise HTTPException(401, "GitHub authorization failed.")
        access = token.json()["access_token"]
        headers={"Authorization":f"Bearer {access}","Accept":"application/vnd.github+json"}
        info = await client.get("https://api.github.com/user",headers=headers)
        if info.status_code >= 400:
            raise HTTPException(401, "Could not read GitHub account.")
        data=info.json()
        email=data.get("email")
        if not email:
            emails=await client.get("https://api.github.com/user/emails",headers=headers)
            if emails.status_code < 400:
                email=next((x.get("email") for x in emails.json() if x.get("primary") and x.get("verified")),None)
        if not email:
            raise HTTPException(401,"GitHub did not provide a verified email.")
    return {"provider":"github","provider_id":str(data["id"]),"email":email,
            "name":data.get("name") or data.get("login"),"avatar_url":data.get("avatar_url")}

@router.get("/key")
async def get_my_aether_key(current_user: User = Depends(get_current_user)):
    return {"aether_api_key": create_user_api_key(current_user.id, settings.SECRET_KEY), "user_id": current_user.id}

@router.post("/guest", response_model=GuestResponse)
async def create_guest(db: AsyncSession = Depends(get_db)):
    token, limit = await create_guest_session(db)
    return GuestResponse(access_token=token, messages_remaining=limit, max_messages=limit)
