from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import httpx

from app.core.config import settings
from app.core.security import create_access_token, get_current_user
from app.db.base import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.get("/google/login")
async def google_login():
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(400, "Google OAuth is not configured on the server yet.")
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        "&response_type=code&scope=openid%20email%20profile"
        "&access_type=offline&prompt=consent"
    )
    return {"login_url": url}


@router.get("/github/login")
async def github_login():
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(400, "GitHub OAuth is not configured on the server yet.")
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
        "&scope=user:email"
    )
    return {"login_url": url}


class OAuthCodeExchange(BaseModel):
    """Client sends the authorization CODE from the provider redirect.
    Backend independently verifies it with Google/GitHub before issuing a JWT.
    """
    provider: str = Field(..., pattern="^(google|github)$")
    code: str = Field(..., min_length=10, max_length=2048)


async def _verify_google(code: str) -> dict:
    """Exchange Google auth code for tokens and fetch userinfo. Raises on failure."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(500, "Google OAuth is not fully configured on the server.")

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code >= 400:
            raise HTTPException(401, f"Google token exchange failed: {token_resp.text[:300]}")
        tokens = token_resp.json()
        access = tokens.get("access_token")
        if not access:
            raise HTTPException(401, "Google did not return an access token.")

        info_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access}"},
        )
        if info_resp.status_code >= 400:
            raise HTTPException(401, "Failed to fetch Google user info.")
        info = info_resp.json()

    sub = info.get("sub")
    email = info.get("email")
    if not sub or not email:
        raise HTTPException(401, "Google user info missing sub or email.")
    return {
        "provider": "google",
        "provider_id": str(sub),
        "email": email,
        "name": info.get("name"),
        "avatar_url": info.get("picture"),
    }


async def _verify_github(code: str) -> dict:
    """Exchange GitHub auth code for token and fetch user + primary email."""
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(500, "GitHub OAuth is not fully configured on the server.")

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )
        if token_resp.status_code >= 400:
            raise HTTPException(401, f"GitHub token exchange failed: {token_resp.text[:300]}")
        tokens = token_resp.json()
        access = tokens.get("access_token")
        if not access:
            raise HTTPException(401, f"GitHub did not return an access token: {tokens}")

        headers = {
            "Authorization": f"Bearer {access}",
            "Accept": "application/vnd.github+json",
        }
        user_resp = await client.get("https://api.github.com/user", headers=headers)
        if user_resp.status_code >= 400:
            raise HTTPException(401, "Failed to fetch GitHub user.")
        user = user_resp.json()

        email = user.get("email")
        if not email:
            emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
            if emails_resp.status_code < 400:
                for e in emails_resp.json():
                    if e.get("primary") and e.get("verified"):
                        email = e.get("email")
                        break
                if not email and emails_resp.json():
                    email = emails_resp.json()[0].get("email")

        provider_id = str(user.get("id") or "")
        if not provider_id or not email:
            raise HTTPException(401, "GitHub user info missing id or email.")
        return {
            "provider": "github",
            "provider_id": provider_id,
            "email": email,
            "name": user.get("name") or user.get("login"),
            "avatar_url": user.get("avatar_url"),
        }


@router.post("/exchange", response_model=TokenResponse)
async def exchange_oauth(body: OAuthCodeExchange, db: AsyncSession = Depends(get_db)):
    """
    Secure OAuth exchange.
    Client sends only the authorization `code` from the provider redirect.
    Backend verifies the code directly with Google or GitHub, then creates/updates
    the user and issues a JWT. Client-supplied identity data is never trusted.
    """
    if body.provider == "google":
        identity = await _verify_google(body.code)
    elif body.provider == "github":
        identity = await _verify_github(body.code)
    else:
        raise HTTPException(400, "Unsupported provider.")

    result = await db.execute(
        select(User).where(
            User.provider == identity["provider"],
            User.provider_id == identity["provider_id"],
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=identity["email"],
            name=identity.get("name"),
            avatar_url=identity.get("avatar_url"),
            provider=identity["provider"],
            provider_id=identity["provider_id"],
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.name = identity.get("name") or user.name
        user.avatar_url = identity.get("avatar_url") or user.avatar_url
        user.email = identity["email"] or user.email
        await db.commit()

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "provider": user.provider,
        },
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "provider": user.provider,
    }
