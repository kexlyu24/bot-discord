import discord
import yt_dlp
import asyncio
import random
import logging
from typing import List, Optional, Literal, Union

# Import our options from the config we created earlier
from config import YTDL_OPTIONS, FFMPEG_OPTIONS

logger = logging.getLogger('discord')

# Initialize yt-dlp globally
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# ==========================================
# 1. SONG CLASS
# ==========================================
class Song:
    """Represents a playable audio track."""
    def __init__(
        self, 
        title: str, 
        url: str, 
        stream_url: str, 
        duration: int, 
        thumbnail: str, 
        requester: Union[discord.Member, discord.User], 
        platform: str
    ):
        self.title = title
        self.url = url
        self.stream_url = stream_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
        self.platform = platform.lower()

    @property
    def platform_icon(self) -> str:
        """Returns a string/emoji representing the platform icon for UI embeds."""
        icons = {
            "youtube": "▶️",       # YouTube play button
            "spotify": "🟢",       # Spotify green circle
            "soundcloud": "☁️",   # SoundCloud cloud
            "direct": "🔗",        # Direct URL link
            "search": "🔍"         # Search magnifying glass
        }
        return icons.get(self.platform, "🎵")

# ==========================================
# 2. MUSIC QUEUE MANAGER
# ==========================================
class MusicQueue:
    """Manages the song queue, history, and looping state per guild."""
    def __init__(self):
        self._queue: List[Song] = []
        self._history: List[Song] = []
        self.now_playing: Optional[Song] = None
        self.loop_mode: Literal["off", "song", "queue"] = "off"
        self.player_message: Optional[discord.Message] = None
        self.last_channel: Optional[discord.TextChannel] = None

    def add(self, song: Song):
        """Adds a song to the end of the queue."""
        self._queue.append(song)

    def remove(self, index: int) -> Optional[Song]:
        """Removes a song at the specified 0-based index."""
        if 0 <= index < len(self._queue):
            return self._queue.pop(index)
        return None

    def skip(self, force: bool = False) -> Optional[Song]:
        """
        Advances the queue and returns the next song.
        If force=True, it ignores the 'song' loop mode (used for manual /skip command).
        """
        if self.now_playing:
            self._history.append(self.now_playing)
            # Keep history limited to the last 10 songs
            if len(self._history) > 10:
                self._history.pop(0)
                
            # Handle looping logic only if not a forced skip
            if not force:
                if self.loop_mode == "song":
                    self._queue.insert(0, self.now_playing)
                elif self.loop_mode == "queue":
                    self._queue.append(self.now_playing)
                    
        self.now_playing = self._queue.pop(0) if self._queue else None
        return self.now_playing

    def previous(self) -> Optional[Song]:
        """Reverts to the last played song from history."""
        if not self._history:
            return None
            
        previous_song = self._history.pop()
        
        # Push the currently playing song back to the top of the queue
        if self.now_playing:
            self._queue.insert(0, self.now_playing)
            
        self.now_playing = previous_song
        return self.now_playing

    def shuffle(self):
        """Randomizes the order of the remaining queue."""
        random.shuffle(self._queue)

    def clear(self):
        """Empties the upcoming queue."""
        self._queue.clear()
        
    @property
    def history(self) -> List[Song]:
        """Returns the play history (max 10)."""
        return self._history
        
    @property
    def queue(self) -> List[Song]:
        """Returns the upcoming queue."""
        return self._queue

    @property
    def is_empty(self) -> bool:
        """Checks if the upcoming queue is empty."""
        return len(self._queue) == 0


# ==========================================
# 3. YT-DLP SOURCE HANDLER
# ==========================================
class YTDLSource(discord.PCMVolumeTransformer):
    """Handles extracting streaming URLs via yt-dlp and wrapping them in FFmpegPCMAudio."""
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data

    @classmethod
    async def create_source(cls, stream_url: str, volume=0.5):
        """
        Creates the playable discord FFmpeg object from a direct stream URL.
        FFMPEG_OPTIONS applies the Opus encoding, Buffer, and Reconnect flags.
        """
        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        return cls(source, data=None, volume=volume)

    @classmethod
    async def _extract_info(cls, query: str, loop: asyncio.AbstractEventLoop = None) -> dict:
        """Asynchronously extracts info using yt-dlp to prevent blocking the bot."""
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
            return data
        except Exception as e:
            logger.error(f"yt-dlp extraction error for {query}: {e}")
            raise e

    @classmethod
    async def search_youtube(cls, query: str, requester: Union[discord.Member, discord.User], loop: asyncio.AbstractEventLoop = None) -> Song:
        """Searches YouTube for a query and returns a Song object."""
        # Force ytsearch if a raw URL wasn't provided
        if not query.startswith("ytsearch:"):
            query = f"ytsearch:{query}"
            
        data = await cls._extract_info(query, loop)
        
        if 'entries' in data and len(data['entries']) > 0:
            data = data['entries'][0]
        else:
            raise Exception("No results found on YouTube.")

        return Song(
            title=data.get('title', 'Unknown Title'),
            url=data.get('webpage_url', data.get('url')),
            stream_url=data.get('url'),  # This is the direct expiring stream URL for FFmpeg
            duration=data.get('duration', 0),
            thumbnail=data.get('thumbnail', ''),
            requester=requester,
            platform="youtube"
        )

    @classmethod
    async def from_url(cls, url: str, requester: Union[discord.Member, discord.User], platform: str = "direct", loop: asyncio.AbstractEventLoop = None) -> Song:
        """Extracts data directly from a specific URL."""
        data = await cls._extract_info(url, loop)
        
        # Safety fallback if it accidentally resolved to a playlist
        if 'entries' in data and len(data['entries']) > 0:
            data = data['entries'][0]

        return Song(
            title=data.get('title', 'Unknown Audio'),
            url=data.get('webpage_url', url),
            stream_url=data.get('url'),
            duration=data.get('duration', 0),
            thumbnail=data.get('thumbnail', ''),
            requester=requester,
            platform=platform
        )

    @classmethod
    async def from_soundcloud(cls, url: str, requester: Union[discord.Member, discord.User], loop: asyncio.AbstractEventLoop = None) -> Song:
        """Helper specifically for SoundCloud URLs."""
        return await cls.from_url(url, requester, platform="soundcloud", loop=loop)
