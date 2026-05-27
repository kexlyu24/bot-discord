import httpx
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from urllib.parse import quote
from app.core.config import settings

# ==========================================
# 1. JWT UTILITIES
# ==========================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a secure JWT access token for the dashboard session."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decodes a JWT access token and returns the payload if valid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

# ==========================================
# 2. DISCORD OAUTH2 HELPER METHODS
# ==========================================

API_ENDPOINT = "https://discord.com/api/v10"

def get_oauth_url() -> str:
    """Generates the OAuth2 redirect URL for user authentication via Discord."""
    redirect_uri_escaped = quote(settings.DISCORD_REDIRECT_URI, safe='')
    url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={settings.DISCORD_CLIENT_ID}"
        f"&redirect_uri={redirect_uri_escaped}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return url

async def exchange_code(code: str) -> Optional[str]:
    """Exchanges the authorization code for a Discord bearer access token."""
    data = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "client_secret": settings.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.DISCORD_REDIRECT_URI
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_ENDPOINT}/oauth2/token", data=data, headers=headers)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None

async def get_discord_user(token: str) -> Optional[dict]:
    """Retrieves user profile information (@me) using the Discord access token."""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_ENDPOINT}/users/@me", headers=headers)
        if response.status_code == 200:
            return response.json()
        return None

async def get_user_guilds(token: str) -> Optional[list]:
    """Retrieves the list of guilds the user is in using the Discord access token."""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_ENDPOINT}/users/@me/guilds", headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
