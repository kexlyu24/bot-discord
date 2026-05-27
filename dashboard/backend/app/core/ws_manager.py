import time
import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger('discord')

class WebSocketManager:
    def __init__(self):
        # Maps guild_id (int) to list of WebSockets
        self.connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, guild_id: int, websocket: WebSocket):
        """Accepts the WebSocket connection and appends it to the guild's room."""
        await websocket.accept()
        if guild_id not in self.connections:
            self.connections[guild_id] = []
        self.connections[guild_id].append(websocket)
        logger.info(f"WebSocket client connected to guild room {guild_id}")

    async def disconnect(self, guild_id: int, websocket: WebSocket):
        """Removes the WebSocket connection from the guild's room."""
        if guild_id in self.connections:
            if websocket in self.connections[guild_id]:
                self.connections[guild_id].remove(websocket)
            if not self.connections[guild_id]:
                del self.connections[guild_id]
        logger.info(f"WebSocket client disconnected from guild room {guild_id}")

    async def broadcast(self, guild_id: int, data: dict):
        """Broadcasts a JSON payload to all connected clients in a specific guild room."""
        g_id = int(guild_id)
        if g_id in self.connections:
            # Create a copy of the list to prevent modification during iteration
            for connection in list(self.connections[g_id]):
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error broadcasting to WebSocket in guild {g_id}: {e}")

    async def broadcast_all(self, data: dict):
        """Broadcasts a JSON payload to all connected clients across all guilds (e.g. admin notices)."""
        for g_id, ws_list in list(self.connections.items()):
            for connection in list(ws_list):
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error broadcasting to WebSocket in guild {g_id} (global): {e}")

# Global singleton instance
ws_manager = WebSocketManager()

def get_player_state_data(guild_id, bot) -> dict:
    """Helper method to construct the full player state payload from shared memory queues."""
    from shared_state import queues
    import discord
    
    # Ensure guild_id is int (queues dict is keyed by int)
    g_id = int(guild_id)
    
    
    if g_id not in queues:
        return {
            "is_playing": False,
            "is_paused": False,
            "now_playing": None,
            "queue": [],
            "volume": 50,
            "loop_mode": "off",
            "queue_count": 0
        }
        
    q = queues[g_id]
    bot_guild = bot.get_guild(g_id) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    
    is_playing = bot_voice.is_playing() if bot_voice else False
    is_paused = bot_voice.is_paused() if bot_voice else False
    # Calculate progress (with None-safety for duration)
    progress = 0
    if q.now_playing and hasattr(q, "start_time") and q.start_time:
        duration = q.now_playing.duration or 0
        progress = min(duration, int(time.time() - q.start_time))
        
    now_playing_data = None
    if q.now_playing:
        try:
            requester_name = q.now_playing.requester.name if q.now_playing.requester else "Unknown"
        except Exception:
            requester_name = "Unknown"
        
        now_playing_data = {
            "title": q.now_playing.title,
            "url": q.now_playing.url,
            "platform": q.now_playing.platform,
            "thumbnail": q.now_playing.thumbnail,
            "duration": q.now_playing.duration or 0,
            "progress": progress,
            "requester": requester_name
        }
        
    queue_list = []
    for s in q.queue:
        try:
            req_name = s.requester.name if s.requester else "Unknown"
        except Exception:
            req_name = "Unknown"
        queue_list.append({
            "title": s.title,
            "url": s.url,
            "platform": s.platform,
            "thumbnail": s.thumbnail,
            "duration": s.duration or 0,
            "requester": req_name
        })
        
    volume = 50
    if bot_voice and bot_voice.source:
        volume = int(getattr(bot_voice.source, "volume", 0.5) * 100)
        
    return {
        "is_playing": is_playing,
        "is_paused": is_paused,
        "now_playing": now_playing_data,
        "queue": queue_list,
        "volume": volume,
        "loop_mode": q.loop_mode,
        "queue_count": len(queue_list)
    }

