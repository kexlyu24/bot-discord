import os
import sys
import time
import psutil
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

# Dynamically append root path to ensure cogs and utils imports
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from shared_state import queues
from app.core.dependencies import get_admin_user, get_db
from app.models.settings import GuildSettings

router = APIRouter()

# Track startup timestamp for bot uptime calculation
START_TIME = time.time()

@router.get("/health")
async def get_system_health(current_user: dict = Depends(get_admin_user)):
    """Retrieves host system diagnostics (CPU, RAM, Uptime) for administrator review."""
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # Virtual memory details
        vm = psutil.virtual_memory()
        ram_percent = vm.percent
        ram_used_mb = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
        ram_total_mb = int(vm.total / (1024 * 1024))
        
        uptime_seconds = int(time.time() - START_TIME)
        
        return {
            "success": True,
            "data": {
                "cpu_percent": cpu_percent,
                "ram_used_mb": ram_used_mb,
                "ram_total_mb": ram_total_mb,
                "ram_percent": ram_percent,
                "uptime_seconds": uptime_seconds
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system metrics: {e}"
        )

@router.get("/servers")
async def get_bot_servers(request: Request, current_user: dict = Depends(get_admin_user)):
    """Lists all Discord servers (guilds) the bot is currently a member of."""
    bot = getattr(request.app.state, "bot", None)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord bot instance is not running."
        )
        
    servers_list = []
    for guild in bot.guilds:
        # Check active queues for guild
        is_playing = False
        queue_count = 0
        if guild.id in queues:
            is_playing = queues[guild.id].now_playing is not None
            queue_count = len(queues[guild.id].queue)
            
        servers_list.append({
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count,
            "active_queue_count": queue_count,
            "is_playing": is_playing
        })
        
    return {"success": True, "data": servers_list}

@router.delete("/servers/{guild_id}")
async def force_leave_server(guild_id: str, request: Request, current_user: dict = Depends(get_admin_user)):
    """Instructs the bot to leave a specific Discord guild."""
    bot = getattr(request.app.state, "bot", None)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord bot instance is not running."
        )
        
    try:
        g_id = int(guild_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid guild ID format.")
        
    guild = bot.get_guild(g_id)
    if not guild:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot is not in the specified guild."
        )
        
    try:
        # Disconnect any active voice clients in the guild first
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
            
        await guild.leave()
        queues.pop(g_id, None)  # Clean up memory queue
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to leave guild: {e}"
        )
