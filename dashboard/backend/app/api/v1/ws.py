import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_access_token
from app.core.ws_manager import ws_manager, get_player_state_data

logger = logging.getLogger('discord')
router = APIRouter()

@router.websocket("/client/{guild_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    guild_id: str,
    token: Optional[str] = Query(None)
):
    """Establishes a real-time WebSocket connection to sync player state for a specific guild."""
    # 1. Validate JWT from token query param (since WebSockets don't pass Cookie header natively in some contexts)
    if not token:
        logger.warning("WebSocket connection rejected: Token is missing.")
        await websocket.close(code=1008)  # Policy Violation
        return
        
    payload = decode_access_token(token)
    if not payload:
        logger.warning("WebSocket connection rejected: Token validation failed.")
        await websocket.close(code=1008)
        return
        
    # 2. Verify user guild membership
    user_guilds = payload.get("guilds", [])
    if not any(g["id"] == guild_id for g in user_guilds):
        logger.warning(f"WebSocket connection rejected: User {payload.get('user_id')} not in guild {guild_id}.")
        await websocket.close(code=1008)
        return
        
    # 3. Add to WebSocket manager connection registry
    g_id = int(guild_id)
    await ws_manager.connect(g_id, websocket)
    
    bot = getattr(websocket.app.state, "bot", None)
    # 4. Immediately send current player state on connect
    try:
        initial_state = get_player_state_data(g_id, bot)
        await websocket.send_json({
            "event": "state_update",
            "guild_id": str(g_id),
            "data": initial_state
        })
    except Exception as e:
        logger.error(f"[WS] Error sending initial state for guild {g_id}: {e}", exc_info=True)
        
    # 5. Keep alive loop (ping/pong every 30 seconds)
    try:
        while True:
            try:
                # Wait for client messages (or ping responses) with a 30s timeout
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if message == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Idle timeout reached -> send a ping frame to client to keep connection open
                try:
                    await websocket.send_json({"event": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup connection on disconnect
        await ws_manager.disconnect(g_id, websocket)
