
from fastapi import Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.core.security import decode_access_token
from app.core.database import get_db as db_generator


def get_db():
    """Database session dependency."""
    yield from db_generator()

def get_current_user(request: Request) -> dict:
    """FastAPI dependency to extract and validate the JWT from Authorization header or cookie."""
    token = None
    
    # Primary: Authorization Bearer header (used by frontend localStorage flow)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    
    # Fallback 1: custom X-Auth-Token header (backup if proxy strips Authorization)
    if not token:
        x_token = request.headers.get("x-auth-token", "")
        if x_token:
            token = x_token
    
    # Fallback 2: cookie (for backwards compatibility)
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Access token is missing."
        )
        
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again."
        )
    return payload

def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency to enforce administrator role verification."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Bot owner privileges are required."
        )
    return current_user

