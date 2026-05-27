import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

# Dynamically append root path to ensure smooth cogs/utils imports
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import discord
from shared_state import queues
from app.core.dependencies import get_current_user, get_db
from app.models.settings import GuildSettings

router = APIRouter()

class GuildSettingsUpdate(BaseModel):
    dj_role_id: Optional[str] = None
    default_volume: Optional[int] = None

@router.get("/")
async def get_guilds(request: Request, current_user: dict = Depends(get_current_user)):
    """Retrieves all servers where the user is a member and the bot is present."""
    bot = getattr(request.app.state, "bot", None)
    filtered_guilds = []
    
    for g in current_user.get("guilds", []):
        g_id = int(g["id"])
        
        # Check if the bot is present in the server
        bot_guild = bot.get_guild(g_id) if bot else None
        has_bot = bot_guild is not None
        
        # Filter: only show guilds where the bot is joined or has active queues
        if has_bot or g_id in queues:
            is_playing = False
            if g_id in queues:
                is_playing = queues[g_id].now_playing is not None
                
            filtered_guilds.append({
                "id": g["id"],
                "name": g["name"],
                "icon": g.get("icon"),
                "has_bot": has_bot,
                "is_playing": is_playing
            })
            
    return {"success": True, "data": filtered_guilds}

@router.get("/{guild_id}")
async def get_guild_details(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Retrieves detailed information (member count, voice/text channels) for a specific server."""
    # 1. Validate user is a member of the requested guild
    user_guilds = current_user.get("guilds", [])
    if not any(g["id"] == guild_id for g in user_guilds):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden. You are not a member of this server."
        )
        
    bot = getattr(request.app.state, "bot", None)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord bot instance is not connected."
        )
        
    bot_guild = bot.get_guild(int(guild_id))
    if not bot_guild:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot is not in this guild."
        )
        
    # 2. Map server text and voice channels
    voice_channels = []
    text_channels = []
    for channel in bot_guild.channels:
        if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            voice_channels.append({"id": str(channel.id), "name": channel.name})
        elif isinstance(channel, discord.TextChannel):
            text_channels.append({"id": str(channel.id), "name": channel.name})
            
    return {
        "success": True,
        "data": {
            "id": str(bot_guild.id),
            "name": bot_guild.name,
            "icon": bot_guild.icon.url if bot_guild.icon else None,
            "member_count": bot_guild.member_count,
            "voice_channels": voice_channels,
            "text_channels": text_channels
        }
    }

@router.get("/{guild_id}/settings")
async def get_guild_settings(guild_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetches custom volume and DJ role configurations for the guild."""
    # Validate membership
    user_guilds = current_user.get("guilds", [])
    if not any(g["id"] == guild_id for g in user_guilds):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden. You are not a member of this server."
        )
        
    db_settings = db.query(GuildSettings).filter(GuildSettings.guild_id == guild_id).first()
    if not db_settings:
        return {
            "success": True,
            "data": {
                "dj_role_id": None,
                "default_volume": 50
            }
        }
        
    return {
        "success": True,
        "data": {
            "dj_role_id": db_settings.dj_role_id,
            "default_volume": db_settings.default_volume
        }
    }

@router.patch("/{guild_id}/settings")
async def update_guild_settings(
    guild_id: str, 
    settings_update: GuildSettingsUpdate,
    current_user: dict = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Updates the server settings (requires user to have Manage Guild permissions)."""
    # 1. Verify membership and extract guild permissions
    guild_entry = next((g for g in current_user.get("guilds", []) if g["id"] == guild_id), None)
    if not guild_entry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden. You are not a member of this server."
        )
        
    perms = int(guild_entry.get("permissions", 0))
    # Check for MANAGE_GUILD (0x20) or ADMINISTRATOR (0x8)
    is_admin_or_manager = (perms & 0x20) == 0x20 or (perms & 0x8) == 0x8
    
    # Allow update if the user has permissions OR is the bot owner
    if not is_admin_or_manager and not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You require Manage Server or Admin permission to edit settings."
        )
        
    # 2. Get or initialize settings
    db_settings = db.query(GuildSettings).filter(GuildSettings.guild_id == guild_id).first()
    if not db_settings:
        db_settings = GuildSettings(
            guild_id=guild_id,
            dj_role_id=None,
            default_volume=50
        )
        db.add(db_settings)
        db.flush()
        
    # 3. Apply updates
    if settings_update.dj_role_id is not None:
        db_settings.dj_role_id = settings_update.dj_role_id or None
    if settings_update.default_volume is not None:
        db_settings.default_volume = max(0, min(100, settings_update.default_volume))
        
    db.commit()
    db.refresh(db_settings)
    
    return {
        "success": True,
        "data": {
            "dj_role_id": db_settings.dj_role_id,
            "default_volume": db_settings.default_volume
        }
    }
