
from fastapi import APIRouter, Depends, Response, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from app.core.security import get_oauth_url, exchange_code, get_discord_user, get_user_guilds, create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_user


router = APIRouter()

@router.get("/login")
async def login():
    """Returns the Discord OAuth2 authorization URL."""
    oauth_url = get_oauth_url()
    return {"success": True, "data": {"url": oauth_url}}

@router.get("/callback")
async def callback(code: str):
    """Exchanges code for access token, generates JWT, and redirects with token in URL."""
    # 1. Exchange OAuth2 authorization code for Discord token
    access_token = await exchange_code(code)
    if not access_token:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?error=oauth_failed")
    
    # 2. Fetch User identity and joined guilds from Discord API
    user_info = await get_discord_user(access_token)
    user_guilds = await get_user_guilds(access_token)
    if not user_info:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?error=fetch_user_failed")
        
    user_id = user_info.get("id")
    username = user_info.get("username")
    avatar = user_info.get("avatar")
    
    # 3. Determine bot owner privilege state
    is_admin = (user_id == settings.ADMIN_DISCORD_ID)
    
    # 4. Strip guild details to keep JWT payload lightweight
    guilds_data = []
    if user_guilds:
        for g in user_guilds:
            guilds_data.append({
                "id": g.get("id"),
                "name": g.get("name"),
                "icon": g.get("icon"),
                "permissions": str(g.get("permissions", 0))
            })
            
    # 5. Generate Access Token JWT
    token_payload = {
        "user_id": user_id,
        "username": username,
        "avatar": avatar,
        "is_admin": is_admin,
        "guilds": guilds_data
    }
    jwt_token = create_access_token(token_payload)
    
    # 6. Redirect to frontend callback page with JWT in URL parameter.
    #    Frontend will store the token in localStorage.
    #    This avoids cross-port cookie issues entirely.
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}",
        status_code=302
    )

@router.post("/logout")
async def logout():
    """Logout endpoint. Frontend clears localStorage; this is a no-op confirmation."""
    return {"success": True}

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Retrieves session profile info of the currently logged-in user."""
    return {
        "success": True,
        "data": {
            "id": current_user.get("user_id"),
            "username": current_user.get("username"),
            "avatar": current_user.get("avatar"),
            "is_admin": current_user.get("is_admin")
        }
    }

