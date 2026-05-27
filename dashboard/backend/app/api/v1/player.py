import sys
import os
import time
import asyncio
import concurrent.futures
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Dynamically append root path to ensure cogs and utils imports
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import discord
from shared_state import queues
from utils.music_engine import MusicQueue, YTDLSource, Song
from utils.platform_detector import detect_platform
from app.core.dependencies import get_current_user, get_db
from app.models.settings import GuildSettings, BannedSongs
from app.core.ws_manager import ws_manager, get_player_state_data

logger = logging.getLogger('discord')
router = APIRouter()

# ==========================================
# MOCK OBJECTS FOR WEB PLAYBACK CALLBACKS
# ==========================================

class DummyChannel:
    """Mock text channel to swallow error logs if callback channel is missing."""
    async def send(self, *args, **kwargs):
        pass

class WebInteractionMock:
    """Mock discord.Interaction to integrate directly with start_playback/play_next."""
    def __init__(self, guild: discord.Guild, channel=None):
        self.guild = guild
        self.guild_id = guild.id
        self.channel = channel or DummyChannel()

# ==========================================
# REQUEST BODIES
# ==========================================

class PlayRequest(BaseModel):
    query: str

class VolumeRequest(BaseModel):
    level: int

class LoopRequest(BaseModel):
    mode: Literal["off", "song", "queue"]

# ==========================================
# HELPERS
# ==========================================

def get_guild_queue(guild_id: str) -> MusicQueue:
    """Retrieves the live guild queue from shared memory or raises 404."""
    try:
        g_id = int(guild_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guild ID format."
        )
        
    if g_id not in queues:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot is not active in this server."
        )
    return queues[g_id]

def validate_user_in_guild(guild_id: str, current_user: dict):
    """Verifies that the user is a member of the guild via their session guilds."""
    user_guilds = current_user.get("guilds", [])
    if not any(g["id"] == guild_id for g in user_guilds):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden. You are not a member of this server."
        )

async def broadcast_player_state(guild_id: str, bot, event_type: str = "state_update"):
    """Helper to broadcast current player state over WebSockets."""
    try:
        state_data = get_player_state_data(guild_id, bot)
        await ws_manager.broadcast(guild_id, {
            "event": event_type,
            "guild_id": guild_id,
            "data": state_data
        })
    except Exception as e:
        logger.error(f"Failed to broadcast player state update in guild {guild_id}: {e}")

# ==========================================
# ENDPOINTS
# ==========================================

@router.get("/{guild_id}/state")
async def get_player_state(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Fetches the complete real-time playback state of the guild's bot."""
    validate_user_in_guild(guild_id, current_user)
    get_guild_queue(guild_id)  # Validate queue is active
    
    bot = getattr(request.app.state, "bot", None)
    state_data = get_player_state_data(guild_id, bot)
    return {
        "success": True,
        "data": state_data
    }

@router.post("/{guild_id}/play")
async def play_song(
    guild_id: str,
    play_req: PlayRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enqueues a song matching query or URL using shared memory engines."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    bot_guild = bot.get_guild(int(guild_id)) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    if not bot_voice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot must be connected to a voice channel to receive play commands."
        )
        
    # 1. Validate query against banned_songs database rules
    banned = db.query(BannedSongs).filter(BannedSongs.guild_id == guild_id).all()
    for b in banned:
        if b.query.lower() in play_req.query.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This query is blacklisted: {b.query}"
            )
            
    music_cog = bot.get_cog("Music")
    if not music_cog:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Music Cog is not loaded."
        )
        
    # Mock user details
    class RequesterMock:
        def __init__(self, uid, uname):
            self.id = int(uid)
            self.name = uname
            self.display_name = uname
            self.mention = f"<@{uid}>"
            self.display_avatar = None
            self.avatar = None
    requester = RequesterMock(current_user["user_id"], current_user["username"])
    
    platform = detect_platform(play_req.query)
    added_songs = []
    bot_loop = bot.loop
    
    # 2. Resolve URLs/Searches to Song entities
    #    All async resolution calls must run on the bot's event loop
    #    since FastAPI runs in a separate thread with its own loop.
    try:
        if platform == "spotify":
            if not music_cog.spotify.sp:
                raise HTTPException(status_code=400, detail="Spotify API is not configured.")
            if "track" in play_req.query:
                t = music_cog.spotify.get_track(play_req.query)
                song = Song(t['title'], play_req.query, "", t['duration'], t['thumbnail'], requester, "spotify")
                song.artist = t['artist']
                added_songs.append(song)
            elif "album" in play_req.query:
                for t in music_cog.spotify.get_album(play_req.query):
                    song = Song(t['title'], play_req.query, "", t['duration'], t['thumbnail'], requester, "spotify")
                    song.artist = t['artist']
                    added_songs.append(song)
            elif "playlist" in play_req.query:
                future = asyncio.run_coroutine_threadsafe(
                    music_cog.spotify.get_playlist(play_req.query, bot_loop), bot_loop
                )
                tracks = future.result(timeout=30)
                for t in tracks:
                    song = Song(t['title'], play_req.query, "", t['duration'], t['thumbnail'], requester, "spotify")
                    song.artist = t['artist']
                    added_songs.append(song)
        elif platform == "soundcloud":
            future = asyncio.run_coroutine_threadsafe(
                YTDLSource.from_soundcloud(play_req.query, requester, bot_loop), bot_loop
            )
            song = future.result(timeout=30)
            added_songs.append(song)
        elif platform == "direct":
            future = asyncio.run_coroutine_threadsafe(
                YTDLSource.from_url(play_req.query, requester, platform="direct", loop=bot_loop), bot_loop
            )
            song = future.result(timeout=30)
            added_songs.append(song)
        else:
            if play_req.query.startswith("http"):
                future = asyncio.run_coroutine_threadsafe(
                    YTDLSource.from_url(play_req.query, requester, platform="youtube", loop=bot_loop), bot_loop
                )
            else:
                future = asyncio.run_coroutine_threadsafe(
                    YTDLSource.search_youtube(play_req.query, requester, bot_loop), bot_loop
                )
            song = future.result(timeout=30)
            added_songs.append(song)
    except concurrent.futures.TimeoutError:
        logger.error(f"Timeout resolving song for query '{play_req.query}'")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Song resolution timed out. Try again."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving song for query '{play_req.query}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not load audio: {str(e)[:100]}"
        )
        
    if not added_songs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tracks found for query."
        )
        
    # Double-check resolved titles against banlist keywords
    for s in added_songs:
        for b in banned:
            if b.query.lower() in s.title.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Resolved song title '{s.title}' is banned under rule: {b.query}"
                )
                
    # 3. Add to shared memory queue
    for s in added_songs:
        q.add(s)
        
    # Log action
    logger.info(f"User {current_user['user_id']} queued {len(added_songs)} tracks in guild {guild_id} via Web dashboard.")
    
    # 4. Trigger playback automatically if idle
    #    Must use run_coroutine_threadsafe since start_playback
    #    runs on the bot's event loop (different thread).
    if not bot_voice.is_playing() and not bot_voice.is_paused():
        next_song = q.skip()
        if next_song:
            mock_interaction = WebInteractionMock(bot_guild, q.last_channel)
            playback_future = asyncio.run_coroutine_threadsafe(
                music_cog.start_playback(mock_interaction, next_song, q), bot_loop
            )
            try:
                playback_future.result(timeout=15)
            except Exception as e:
                logger.error(f"Error triggering playback in guild {guild_id}: {e}")
            
    # 5. Broadcast queue update to Web clients
    await broadcast_player_state(guild_id, bot, "queue_updated")
            
    return {
        "success": True,
        "data": {
            "song_added": added_songs[0].title,
            "queue_count": len(added_songs)
        }
    }

@router.post("/{guild_id}/pause")
async def pause_song(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Pauses playback."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    bot_guild = bot.get_guild(int(guild_id)) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    
    if not bot_voice:
        raise HTTPException(400, "Bot is not connected to voice.")
    if not bot_voice.is_playing():
        raise HTTPException(409, "Nothing is currently playing to pause.")
        
    try:
        bot_voice.pause()
        logger.info(f"User {current_user['user_id']} paused playback in guild {guild_id}")
        
        # Broadcast state update to Web clients
        await broadcast_player_state(guild_id, bot)
        
        return {"success": True, "is_paused": True}
    except Exception as e:
        logger.error(f"Voice pause error: {e}")
        raise HTTPException(500, f"Failed to pause: {e}")

@router.post("/{guild_id}/resume")
async def resume_song(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Resumes paused playback."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    bot_guild = bot.get_guild(int(guild_id)) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    
    if not bot_voice:
        raise HTTPException(400, "Bot is not connected to voice.")
    if not bot_voice.is_paused():
        raise HTTPException(409, "Music is not currently paused.")
        
    try:
        bot_voice.resume()
        logger.info(f"User {current_user['user_id']} resumed playback in guild {guild_id}")
        
        # Broadcast state update to Web clients
        await broadcast_player_state(guild_id, bot)
        
        return {"success": True, "is_paused": False}
    except Exception as e:
        logger.error(f"Voice resume error: {e}")
        raise HTTPException(500, f"Failed to resume: {e}")

@router.post("/{guild_id}/skip")
async def skip_song(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Skips the currently playing song."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    bot_guild = bot.get_guild(int(guild_id)) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    
    skipped_song = q.now_playing.title if q.now_playing else "None"
    
    try:
        # Force skip breaks loop mode configuration explicitly
        next_song = q.skip(force=True)
        q.pending_next_song = next_song
        
        if bot_voice and (bot_voice.is_playing() or bot_voice.is_paused()):
            bot_voice.stop()  # Triggers play_next callback asynchronously
            
        logger.info(f"User {current_user['user_id']} skipped song in guild {guild_id}")
        
        # Broadcast state update to Web clients
        await broadcast_player_state(guild_id, bot, "song_ended")
        
        return {
            "success": True,
            "data": {
                "skipped_song": skipped_song,
                "now_playing": next_song.title if next_song else None
            }
        }
    except Exception as e:
        logger.error(f"Voice skip error: {e}")
        raise HTTPException(500, f"Failed to skip: {e}")

@router.post("/{guild_id}/previous")
async def previous_song(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Returns to the previous song in the guild's playback history."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    bot_guild = bot.get_guild(int(guild_id)) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    
    prev_song = q.previous()
    if not prev_song:
        raise HTTPException(400, "No playback history to go back to.")
        
    try:
        q.pending_next_song = prev_song
        if bot_voice and (bot_voice.is_playing() or bot_voice.is_paused()):
            bot_voice.stop()  # Triggers play_next callback asynchronously
        else:
            # Manually start playback if client was fully idle
            music_cog = bot.get_cog("Music")
            if music_cog:
                mock_interaction = WebInteractionMock(bot_guild, q.last_channel)
                await music_cog.start_playback(mock_interaction, prev_song, q)
                
        logger.info(f"User {current_user['user_id']} played previous song in guild {guild_id}")
        
        # Broadcast state update to Web clients
        await broadcast_player_state(guild_id, bot)
        
        return {
            "success": True,
            "data": {
                "now_playing": prev_song.title
            }
        }
    except Exception as e:
        logger.error(f"Voice previous error: {e}")
        raise HTTPException(500, f"Failed to return to previous: {e}")

@router.post("/{guild_id}/stop")
async def stop_player(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Stops playback and clears the active queue."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    bot_guild = bot.get_guild(int(guild_id)) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    
    try:
        q.clear()
        q.pending_next_song = None
        
        if bot_voice:
            bot_voice.stop()
            
        logger.info(f"User {current_user['user_id']} stopped player in guild {guild_id}")
        
        # Broadcast player stopped event
        await broadcast_player_state(guild_id, bot, "player_stopped")
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Voice stop error: {e}")
        raise HTTPException(500, f"Failed to stop: {e}")

@router.post("/{guild_id}/volume")
async def set_volume(
    guild_id: str,
    vol_req: VolumeRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Sets the playback volume (0-100)."""
    validate_user_in_guild(guild_id, current_user)
    get_guild_queue(guild_id)  # Validate queue active
    
    bot = getattr(request.app.state, "bot", None)
    bot_guild = bot.get_guild(int(guild_id)) if bot else None
    bot_voice = bot_guild.voice_client if bot_guild else None
    
    if not bot_voice or not bot_voice.source:
        raise HTTPException(400, "No active audio stream to adjust volume.")
        
    try:
        level = max(0, min(100, vol_req.level))
        bot_voice.source.volume = level / 100.0
        logger.info(f"User {current_user['user_id']} set volume to {level}% in guild {guild_id}")
        
        # Broadcast update
        await broadcast_player_state(guild_id, bot)
        
        return {"success": True, "data": {"volume": level}}
    except Exception as e:
        logger.error(f"Voice volume error: {e}")
        raise HTTPException(500, f"Failed to adjust volume: {e}")

@router.post("/{guild_id}/loop")
async def set_loop_mode(
    guild_id: str,
    loop_req: LoopRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Sets the queue loop mode."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    q.loop_mode = loop_req.mode
    logger.info(f"User {current_user['user_id']} set loop mode to {loop_req.mode} in guild {guild_id}")
    
    # Broadcast update
    await broadcast_player_state(guild_id, bot)
    
    return {"success": True, "data": {"loop_mode": loop_req.mode}}

@router.post("/{guild_id}/shuffle")
async def shuffle_queue(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Shuffles the upcoming queue."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    bot = getattr(request.app.state, "bot", None)
    q.shuffle()
    logger.info(f"User {current_user['user_id']} shuffled queue in guild {guild_id}")
    
    # Broadcast update
    await broadcast_player_state(guild_id, bot, "queue_updated")
    
    return {"success": True}

@router.post("/{guild_id}/lyrics")
async def get_song_lyrics(guild_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Fetches lyrics for the currently playing song."""
    validate_user_in_guild(guild_id, current_user)
    q = get_guild_queue(guild_id)
    
    if not q.now_playing:
        raise HTTPException(400, "No song is currently playing.")
    
    # Check Genius API token configuration
    from config import GENIUS_API_TOKEN
    if not GENIUS_API_TOKEN:
        return {
            "success": False,
            "error": "Genius API token not configured. Add GENIUS_API_TOKEN to .env"
        }
        
    bot = getattr(request.app.state, "bot", None)
    music_cog = bot.get_cog("Music") if bot else None
    if not music_cog or not music_cog.lyrics:
        return {
            "success": False,
            "error": "Lyrics service is not initialized. Check GENIUS_API_TOKEN in .env"
        }
        
    search_title = q.now_playing.title
    search_artist = getattr(q.now_playing, 'artist', '')
    
    try:
        from utils.lyrics_handler import LyricsServiceError
        
        # Use run_coroutine_threadsafe to execute on bot's event loop
        future = asyncio.run_coroutine_threadsafe(
            bot.loop.run_in_executor(
                None, music_cog.lyrics.get_lyrics, search_title, search_artist
            ),
            bot.loop
        )
        song_info = future.result(timeout=15)
        
        if not song_info or not song_info.get("lyrics"):
            return {
                "success": False,
                "error": f"Lyrics not found for '{search_title}'"
            }
            
        logger.info(f"User {current_user['user_id']} fetched lyrics for '{search_title}' in guild {guild_id}")
        return {
            "success": True,
            "data": {
                "title": song_info.get("title", search_title),
                "artist": song_info.get("artist", search_artist),
                "lyrics": song_info["lyrics"],
                "url": song_info.get("url", "")
            }
        }
    except concurrent.futures.TimeoutError:
        logger.error(f"Lyrics fetch timed out for '{search_title}'")
        return {
            "success": False,
            "error": "Lyrics fetch timed out. Try again."
        }
    except LyricsServiceError as e:
        logger.error(f"LyricsServiceError for '{search_title}': {e}")
        return {
            "success": False,
            "error": "Lyrics service is currently unavailable."
        }
    except Exception as e:
        logger.error(f"Unexpected error fetching lyrics for '{search_title}': {e}")
        return {
            "success": False,
            "error": f"Failed to load lyrics: {str(e)[:100]}"
        }
