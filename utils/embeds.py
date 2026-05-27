import discord
import time
from typing import List, Optional

from config import COLORS
from utils.music_engine import Song, MusicQueue

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def format_duration(seconds: int) -> str:
    """Converts seconds to M:SS or H:MM:SS format."""
    if seconds <= 0:
        return "Live / Unknown"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def generate_progress_bar(elapsed: int, total: int, bar_length: int = 15) -> str:
    """
    Generates a textual progress bar.
    Format: ▶ ━━━━━●──────── 1:23 / 3:45
    """
    if total <= 0:
        return "▶ " + "━" * bar_length + " Live"
        
    progress = min(max(elapsed / total, 0.0), 1.0)
    filled = int(bar_length * progress)
    
    # Ensure exact length of bar string
    bar = "━" * filled + "●" + "─" * max(0, bar_length - filled - 1)
    return f"▶ {bar} {format_duration(elapsed)} / {format_duration(total)}"


# ==========================================
# CORE EMBEDS
# ==========================================

def create_error_embed(message: str) -> discord.Embed:
    """Generates a standard red error embed."""
    return discord.Embed(description=f"❌ {message}", color=COLORS.get('error', 0xe74c3c))

def create_success_embed(message: str) -> discord.Embed:
    """Generates a standard green success embed."""
    return discord.Embed(description=f"✅ {message}", color=COLORS.get('success', 0x2ecc71))

def create_now_playing_embed(queue: MusicQueue) -> discord.Embed:
    """Generates the advanced Now Playing embed with progress tracking."""
    song = queue.now_playing
    if not song:
        return create_error_embed("Nothing is currently playing.")
        
    color = COLORS.get(song.platform, COLORS.get('default', 0x3498db))
    
    embed = discord.Embed(
        title="Now Playing", 
        description=f"{song.platform_icon} **[{song.title}]({song.url})**\n*Platform: {song.platform.capitalize()}*",
        color=color
    )
    
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
        
    # Calculate elapsed time from the MusicQueue state
    elapsed = 0
    if hasattr(queue, 'start_time'):
        elapsed = int(time.time() - getattr(queue, 'start_time'))
        
    progress_bar = generate_progress_bar(elapsed, song.duration)
    embed.add_field(name="Progress", value=f"`{progress_bar}`", inline=False)
    
    # Requester Details (Avatar + Name)
    requester = song.requester
    avatar = getattr(requester, 'display_avatar', None)
    if avatar is None:
        avatar = getattr(requester, 'avatar', None)
    avatar_url = avatar.url if avatar else None
    
    display_name = getattr(requester, 'display_name', requester.name)
    embed.set_author(name=f"Requested by {display_name}", icon_url=avatar_url)
    
    # Status Footers
    loop_icons = {"off": "➡️ Off", "song": "🔂 Song", "queue": "🔁 Queue"}
    embed.add_field(name="Loop Mode", value=f"`{loop_icons.get(queue.loop_mode, 'Off')}`", inline=True)
    embed.add_field(name="Up Next", value=f"`{len(queue.queue)} songs`", inline=True)
    
    return embed

def create_queue_embed(queue: MusicQueue, page: int = 1) -> discord.Embed:
    """Generates a paginated embed showing current queue status."""
    if queue.is_empty and not queue.now_playing:
        return discord.Embed(title="🎶 Current Queue", description="*The queue is entirely empty.*", color=COLORS.get('default', 0x3498db))
        
    embed = discord.Embed(title="🎶 Current Queue", color=COLORS.get('default', 0x3498db))
    desc = ""
    
    # Top section: Currently playing
    if queue.now_playing:
        np = queue.now_playing
        desc += f"**Now Playing:**\n{np.platform_icon} [{np.title}]({np.url}) | `{format_duration(np.duration)}`\n\n"
        
    if queue.is_empty:
        desc += "**Up Next:**\n*Nothing in queue.*"
        embed.description = desc
        total_duration = queue.now_playing.duration if queue.now_playing else 0
        embed.set_footer(text=f"Page 1/1 • Total Duration: {format_duration(total_duration)}")
        return embed
        
    # Bottom section: Up next list (Paginated)
    start = (page - 1) * 10
    end = start + 10
    q_slice = queue.queue[start:end]
    
    desc += "**Up Next:**\n"
    for i, song in enumerate(q_slice, start=start+1):
        desc += f"`{i}.` {song.platform_icon} [{song.title}]({song.url}) | `{format_duration(song.duration)}`\n"
        
    embed.description = desc
    
    # Totals computation
    total_duration = sum(s.duration for s in queue.queue)
    if queue.now_playing:
        total_duration += queue.now_playing.duration
        
    max_pages = max(1, (len(queue.queue) + 9) // 10)
    embed.set_footer(text=f"Page {page}/{max_pages} • Total Duration: {format_duration(total_duration)}")
    
    return embed

def create_added_song_embed(song: Song, position: int) -> discord.Embed:
    """Generates an embed showing a single song added to the queue."""
    embed = discord.Embed(
        title="Added to Queue",
        description=f"{song.platform_icon} **[{song.title}]({song.url})**",
        color=COLORS.get(song.platform, COLORS.get('success', 0x2ecc71))
    )
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
        
    embed.add_field(name="Duration", value=f"`{format_duration(song.duration)}`", inline=True)
    embed.add_field(name="Position", value=f"`#{position}`", inline=True)
    return embed

def create_added_playlist_embed(name: str, url: str, platform: str, track_count: int, total_duration: int) -> discord.Embed:
    """Generates an embed showing a bulk playlist or album added to the queue."""
    icons = {
        "youtube": "▶️",
        "spotify": "🟢",
        "soundcloud": "☁️",
        "direct": "🔗",
        "search": "🔍"
    }
    icon = icons.get(platform.lower(), "🎵")
    
    embed = discord.Embed(
        title="Playlist / Album Added",
        description=f"{icon} **[{name}]({url})**",
        color=COLORS.get(platform, COLORS.get('success', 0x2ecc71))
    )
    embed.add_field(name="Tracks Added", value=f"`{track_count}`", inline=True)
    embed.add_field(name="Total Duration", value=f"`{format_duration(total_duration)}`", inline=True)
    return embed
