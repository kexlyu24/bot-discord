import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import math
import time
import logging
from typing import Dict, Optional, Literal

# Set up logging
logger = logging.getLogger('discord')

# Import Custom Handlers & Configs
from config import COLORS, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, GENIUS_API_TOKEN
from utils.lyrics_handler import LyricsHandler, LyricsServiceError
from utils.platform_detector import detect_platform
from utils.spotify_handler import SpotifyHandler, SpotifyError
from utils.music_engine import MusicQueue, YTDLSource, Song
from utils.presence import update_presence
from utils.player_view import PlayerView
from utils.embeds import (
    create_error_embed, create_success_embed, create_now_playing_embed,
    create_queue_embed, create_added_song_embed, create_added_playlist_embed
)

# Import shared queues dictionary (single source of truth)
from shared_state import queues

class QueueView(discord.ui.View):
    """Interactive Discord UI View for paginating the music queue."""
    def __init__(self, queue: list, page: int = 1):
        super().__init__(timeout=120)
        self.queue = queue
        self.page = page
        self.max_pages = math.ceil(len(queue) / 10) or 1
        
    def generate_embed(self):
        # We now use our dedicated embed generator, passing the page
        from utils.embeds import create_queue_embed
        embed = discord.Embed(title="🎶 Current Queue", color=COLORS['default'])
        start = (self.page - 1) * 10
        end = start + 10
        
        q_slice = self.queue[start:end]
        desc = ""
        for i, song in enumerate(q_slice, start=start+1):
            dur = f"{song.duration // 60}:{song.duration % 60:02d}"
            desc += f"`{i}.` {song.platform_icon} [{song.title}]({song.url}) | `{dur}`\n"
            
        embed.description = desc or "The queue is currently empty."
        embed.set_footer(text=f"Page {self.page}/{self.max_pages}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            self.page -= 1
            await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_pages:
            self.page += 1
            await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        else:
            await interaction.response.defer()


class LyricsView(discord.ui.View):
    """Interactive Discord UI View for paginating lyrics."""
    def __init__(self, title: str, artist: str, pages: list[str], url: str, thumbnail: Optional[str] = None):
        super().__init__(timeout=120)
        self.title = title
        self.artist = artist
        self.pages = pages
        self.url = url
        self.thumbnail = thumbnail
        self.page = 1
        self.max_pages = len(pages)
        
    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎤 {self.title} — {self.artist}",
            url=self.url,
            description=self.pages[self.page - 1],
            color=0x9B59B6  # Purple
        )
        if self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail)
        embed.set_footer(text=f"Powered by Genius | Page {self.page} of {self.max_pages}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            self.page -= 1
            await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_pages:
            self.page += 1
            await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        else:
            await interaction.response.defer()

    @staticmethod
    def paginate_lyrics(lyrics: str, max_chars: int = 4000) -> list[str]:
        if not lyrics:
            return ["No lyrics content found."]
        
        pages = []
        current_page = []
        current_length = 0
        
        for line in lyrics.split('\n'):
            if len(line) > max_chars:
                if current_page:
                    pages.append('\n'.join(current_page))
                    current_page = []
                    current_length = 0
                for i in range(0, len(line), max_chars):
                    pages.append(line[i:i+max_chars])
                continue
                
            if current_length + len(line) + 1 > max_chars:
                pages.append('\n'.join(current_page))
                current_page = [line]
                current_length = len(line) + 1
            else:
                current_page.append(line)
                current_length += len(line) + 1
                
        if current_page:
            pages.append('\n'.join(current_page))
            
        return pages


class Music(commands.Cog):
    """Music Cog holding all audio slash commands."""
    def __init__(self, bot):
        self.bot = bot
        self.spotify = SpotifyHandler(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        self.lyrics = LyricsHandler(GENIUS_API_TOKEN)

    def get_queue(self, guild_id: int) -> MusicQueue:
        """Retrieves or instantiates a queue for the given guild."""
        if guild_id not in queues:
            queues[guild_id] = MusicQueue()
        return queues[guild_id]

    async def _ensure_voice(self, interaction: discord.Interaction) -> bool:
        """Validates that user is in a voice channel and bot can join/is joined."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(embed=create_error_embed("You must be in a voice channel to use this command."), ephemeral=True)
            return False
            
        bot_voice = interaction.guild.voice_client
        user_channel = interaction.user.voice.channel
        
        if bot_voice and bot_voice.channel.id != user_channel.id:
            await interaction.response.send_message(embed=create_error_embed(f"You must be in the same voice channel as the bot ({bot_voice.channel.mention})."), ephemeral=True)
            return False
            
        # Verify Bot Permissions before attempting to join
        me = interaction.guild.me
        permissions = user_channel.permissions_for(me)
        if not permissions.connect:
            await interaction.response.send_message(embed=create_error_embed("I do not have permission to **Connect** to your voice channel."), ephemeral=True)
            return False
        if not permissions.speak:
            await interaction.response.send_message(embed=create_error_embed("I do not have permission to **Speak** in your voice channel."), ephemeral=True)
            return False
            
        return True

    def play_next(self, interaction: discord.Interaction, error=None):
        """Callback fired automatically when FFmpeg finishes playing a track."""
        if error:
            logger.error(f"Player error: {error}")
            
        bot_voice = interaction.guild.voice_client
        if not bot_voice: return
            
        q = self.get_queue(interaction.guild_id)
        
        # Override skip logic for manual /skip and /previous commands
        if hasattr(q, "pending_next_song") and getattr(q, "pending_next_song") is not None:
            next_song = q.pending_next_song
            q.pending_next_song = None
        else:
            next_song = q.skip(force=False) 

        if not next_song:
            asyncio.run_coroutine_threadsafe(update_presence(self.bot, None), self.bot.loop)
            
            # Start idle timer when song ends and queue is empty
            voice_events_cog = self.bot.get_cog("VoiceEvents")
            if voice_events_cog:
                voice_events_cog.start_idle_timer(interaction.guild_id, bot_voice)
                
            # Broadcast player_stopped event to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(interaction.guild_id, {
                        "event": "player_stopped",
                        "guild_id": str(interaction.guild_id),
                        "data": state_data
                    }),
                    self.bot.loop
                )
            except ImportError:
                pass
            return # End of queue reached

        asyncio.run_coroutine_threadsafe(self.start_playback(interaction, next_song, q), self.bot.loop)

    async def start_playback(self, interaction: discord.Interaction, song: Song, queue: MusicQueue):
        """Prepares the audio stream and triggers discord voice client."""
        bot_voice = interaction.guild.voice_client
        if not bot_voice:
            return

        try:
            # Cancel idle timer if a new song starts playing
            voice_events_cog = self.bot.get_cog("VoiceEvents")
            if voice_events_cog:
                voice_events_cog.cancel_idle_timer(interaction.guild_id)

            # Lazy Loading: Spotify songs are resolved to YouTube streams just in time for playback
            if song.platform == "spotify":
                query = f"{getattr(song, 'artist', '')} - {song.title} audio"
                yt_song = await YTDLSource.search_youtube(query, song.requester, self.bot.loop)
                song.stream_url = yt_song.stream_url
                # We optionally update duration in case the YT mirror is slightly longer/shorter
                if yt_song.duration > 0:
                    song.duration = yt_song.duration
            
            source = await YTDLSource.create_source(song.stream_url)
            
            # Start timer for /nowplaying progress bar
            queue.start_time = time.time()
            
            # Update presence
            await update_presence(self.bot, song, paused=False)
            
            bot_voice.play(source, after=lambda e: self.play_next(interaction, e))
            
            # Broadcast song_started event to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                await ws_manager.broadcast(interaction.guild_id, {
                    "event": "song_started",
                    "guild_id": str(interaction.guild_id),
                    "data": state_data
                })
            except ImportError:
                pass
            
        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            try:
                from utils.embeds import create_error_embed
                err_msg = f"Skipped **{song.title}**.\nReason: `Age-restricted, unavailable, or deleted.`"
                asyncio.run_coroutine_threadsafe(interaction.channel.send(embed=create_error_embed(err_msg)), self.bot.loop)
            except Exception:
                pass
            self.play_next(interaction) # Skip gracefully if resolving fails


    # ==========================================
    # DISCORD SLASH COMMANDS
    # ==========================================

    @app_commands.command(name="play", description="Plays audio from YouTube, Spotify, SoundCloud, or search.")
    async def play(self, interaction: discord.Interaction, query: str):
        # Defer immediately as searching / scraping can take >3 seconds
        await interaction.response.defer()
        
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        # Cancel idle timer when user uses /play
        voice_events_cog = self.bot.get_cog("VoiceEvents")
        if voice_events_cog:
            voice_events_cog.cancel_idle_timer(interaction.guild_id)

        if not await self._ensure_voice(interaction):
            return

        bot_voice = interaction.guild.voice_client
        if not bot_voice:
            try:
                bot_voice = await interaction.user.voice.channel.connect()
            except discord.ClientException as e:
                return await interaction.followup.send(f"❌ Could not connect to voice channel: {e}")
        
        platform = detect_platform(query)
        added_songs = []
        
        try:
            # --- Platform Parsing ---
            if platform == "spotify":
                if not self.spotify.sp:
                    return await interaction.followup.send(embed=create_error_embed("Spotify API is not configured! Check your bot's `.env` file."))
                    
                if "track" in query:
                    t = self.spotify.get_track(query)
                    song = Song(t['title'], query, "", t['duration'], t['thumbnail'], interaction.user, "spotify")
                    song.artist = t['artist']
                    added_songs.append(song)
                elif "album" in query:
                    for t in self.spotify.get_album(query):
                        song = Song(t['title'], query, "", t['duration'], t['thumbnail'], interaction.user, "spotify")
                        song.artist = t['artist']
                        added_songs.append(song)
                elif "playlist" in query:
                    status_msg = await interaction.followup.send("⏳ Fetching playlist tracks...")
                    
                    async def progress_cb(current, total):
                        try:
                            # Only edit every 100 tracks to avoid ratelimits
                            if current % 100 == 0 or current == total:
                                await status_msg.edit(content=f"⏳ Loading playlist... {current}/{total} tracks")
                        except Exception:
                            pass
                            
                    tracks = await self.spotify.get_playlist(query, self.bot.loop, progress_cb)
                    
                    for t in tracks:
                        song = Song(t['title'], query, "", t['duration'], t['thumbnail'], interaction.user, "spotify")
                        song.artist = t['artist']
                        added_songs.append(song)
                        
                    if len(tracks) >= 500:
                        await interaction.channel.send("⚠️ **Note:** Playlist capped at 500 tracks to ensure bot stability.")
                        
                    await status_msg.delete()
                else:
                    return await interaction.followup.send("❌ Unsupported Spotify URL. Provide a Track, Album, or Playlist.")
                    
            elif platform == "soundcloud":
                song = await YTDLSource.from_soundcloud(query, interaction.user, self.bot.loop)
                added_songs.append(song)
                
            elif platform == "direct":
                song = await YTDLSource.from_url(query, interaction.user, platform="direct", loop=self.bot.loop)
                added_songs.append(song)
                
            else:
                # Fallback to generic YouTube/URL resolving
                if query.startswith("http"):
                    song = await YTDLSource.from_url(query, interaction.user, platform="youtube", loop=self.bot.loop)
                else:
                    song = await YTDLSource.search_youtube(query, interaction.user, self.bot.loop)
                added_songs.append(song)
                
            # --- Enqueueing ---
            total_dur = 0
            for s in added_songs:
                q.add(s)
                total_dur += s.duration
                
            if len(added_songs) == 1:
                s = added_songs[0]
                position = len(q.queue)
                await interaction.followup.send(embed=create_added_song_embed(s, position))
            else:
                await interaction.followup.send(embed=create_added_playlist_embed("Spotify Playlist / Album", query, "spotify", len(added_songs), total_dur))
                
            # Broadcast queue updated to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                await ws_manager.broadcast(interaction.guild_id, {
                    "event": "queue_updated",
                    "guild_id": str(interaction.guild_id),
                    "data": state_data
                })
            except ImportError:
                pass

            # --- Start playback if currently idle ---
            if not bot_voice.is_playing() and not bot_voice.is_paused():
                next_song = q.skip() 
                await self.start_playback(interaction, next_song, q)
                
        except SpotifyError as e:
            await interaction.followup.send(f"❌ **Spotify Error:** {str(e)}")
        except Exception as e:
            await interaction.followup.send(f"❌ **Error:** {str(e)}")


    @app_commands.command(name="pause", description="Pauses current playback.")
    async def pause(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        if bot_voice and bot_voice.is_playing():
            bot_voice.pause()
            if q.now_playing:
                await update_presence(self.bot, q.now_playing, paused=True)
            await interaction.response.send_message("⏸️ **Paused the music.**")
            
            # Broadcast to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                await ws_manager.broadcast(interaction.guild_id, {
                    "event": "state_update",
                    "guild_id": str(interaction.guild_id),
                    "data": state_data
                })
            except ImportError:
                pass
        else:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            

    @app_commands.command(name="resume", description="Resumes paused playback.")
    async def resume(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        if bot_voice and bot_voice.is_paused():
            bot_voice.resume()
            if q.now_playing:
                await update_presence(self.bot, q.now_playing, paused=False)
            await interaction.response.send_message("▶️ **Resumed the music.**")
            
            # Broadcast to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                await ws_manager.broadcast(interaction.guild_id, {
                    "event": "state_update",
                    "guild_id": str(interaction.guild_id),
                    "data": state_data
                })
            except ImportError:
                pass
        else:
            await interaction.response.send_message("❌ The music is not paused.", ephemeral=True)
            

    @app_commands.command(name="stop", description="Stops playback and clears the queue.")
    async def stop(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        
        q.clear()
        q.pending_next_song = None # Reset overrides
        await update_presence(self.bot, None)
        
        if bot_voice:
            bot_voice.stop()
            
        await interaction.response.send_message("⏹️ **Stopped playback and cleared the queue.**")

        # Start idle timer when /stop command used
        voice_events_cog = self.bot.get_cog("VoiceEvents")
        if voice_events_cog and bot_voice:
            voice_events_cog.start_idle_timer(interaction.guild_id, bot_voice)

        # Broadcast player_stopped event to Web clients
        try:
            from app.core.ws_manager import ws_manager, get_player_state_data
            state_data = get_player_state_data(str(interaction.guild_id), self.bot)
            await ws_manager.broadcast(interaction.guild_id, {
                "event": "player_stopped",
                "guild_id": str(interaction.guild_id),
                "data": state_data
            })
        except ImportError:
            pass


    @app_commands.command(name="skip", description="Skips to the next song.")
    async def skip(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        
        # Force skip breaks the song loop explicitly
        next_song = q.skip(force=True)
        q.pending_next_song = next_song
        
        if bot_voice and bot_voice.is_playing():
            bot_voice.stop() # Triggers callback
            await interaction.response.send_message("⏭️ **Skipped.**")
        else:
            await interaction.response.send_message("⏭️ **Skipped.** (Queue advanced manually)")

        # Broadcast song_ended event to Web clients
        try:
            from app.core.ws_manager import ws_manager, get_player_state_data
            state_data = get_player_state_data(str(interaction.guild_id), self.bot)
            await ws_manager.broadcast(interaction.guild_id, {
                "event": "song_ended",
                "guild_id": str(interaction.guild_id),
                "data": state_data
            })
        except ImportError:
            pass


    @app_commands.command(name="previous", description="Goes back to the previous song.")
    async def previous(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        
        prev_song = q.previous()
        if prev_song:
            q.pending_next_song = prev_song
            if bot_voice and bot_voice.is_playing():
                bot_voice.stop()
            await interaction.response.send_message("⏮️ **Going back to previous song.**")
            
            # Broadcast update to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                await ws_manager.broadcast(interaction.guild_id, {
                    "event": "state_update",
                    "guild_id": str(interaction.guild_id),
                    "data": state_data
                })
            except ImportError:
                pass
        else:
            await interaction.response.send_message("❌ No playback history to go back to.", ephemeral=True)


    @app_commands.command(name="queue", description="Shows the current queue.")
    async def queue(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if q.is_empty:
            return await interaction.response.send_message("📭 The queue is currently empty.")
            
        view = QueueView(list(q.queue))
        await interaction.response.send_message(embed=view.generate_embed(), view=view)


    @app_commands.command(name="nowplaying", description="Shows the currently playing song.")
    async def nowplaying(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if not q.now_playing:
            return await interaction.response.send_message(embed=create_error_embed("Nothing is currently playing."), ephemeral=True)
            
        view = PlayerView(self, interaction.guild_id)
        embed = create_now_playing_embed(q)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


    @app_commands.command(name="volume", description="Sets the playback volume (0-100).")
    async def volume(self, interaction: discord.Interaction, level: int):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        
        level = max(0, min(100, level))
        if bot_voice and bot_voice.source:
            bot_voice.source.volume = level / 100.0
            await interaction.response.send_message(f"🔊 **Volume set to {level}%.**")
            
            # Broadcast to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                await ws_manager.broadcast(interaction.guild_id, {
                    "event": "state_update",
                    "guild_id": str(interaction.guild_id),
                    "data": state_data
                })
            except ImportError:
                pass
        else:
            await interaction.response.send_message("❌ Cannot set volume right now (no active playback).", ephemeral=True)


    @app_commands.command(name="loop", description="Sets the loop mode.")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Song", value="song"),
        app_commands.Choice(name="Queue", value="queue")
    ])
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        q.loop_mode = mode.value
        await interaction.response.send_message(f"🔁 **Loop mode set to:** {mode.name}")
        
        # Broadcast to Web clients
        try:
            from app.core.ws_manager import ws_manager, get_player_state_data
            state_data = get_player_state_data(str(interaction.guild_id), self.bot)
            await ws_manager.broadcast(interaction.guild_id, {
                "event": "state_update",
                "guild_id": str(interaction.guild_id),
                "data": state_data
            })
        except ImportError:
            pass


    @app_commands.command(name="shuffle", description="Shuffles the upcoming queue.")
    async def shuffle(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        q.shuffle()
        await interaction.response.send_message("🔀 **Queue shuffled!**")
        
        # Broadcast queue updated to Web clients
        try:
            from app.core.ws_manager import ws_manager, get_player_state_data
            state_data = get_player_state_data(str(interaction.guild_id), self.bot)
            await ws_manager.broadcast(interaction.guild_id, {
                "event": "queue_updated",
                "guild_id": str(interaction.guild_id),
                "data": state_data
            })
        except ImportError:
            pass


    @app_commands.command(name="remove", description="Removes a song from the queue by its index.")
    async def remove(self, interaction: discord.Interaction, index: int):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        song = q.remove(index - 1) 
        if song:
            await interaction.response.send_message(f"🗑️ Removed **{song.title}** from the queue.")
            
            # Broadcast queue updated to Web clients
            try:
                from app.core.ws_manager import ws_manager, get_player_state_data
                state_data = get_player_state_data(str(interaction.guild_id), self.bot)
                await ws_manager.broadcast(interaction.guild_id, {
                    "event": "queue_updated",
                    "guild_id": str(interaction.guild_id),
                    "data": state_data
                })
            except ImportError:
                pass
        else:
            await interaction.response.send_message("❌ Invalid queue index.", ephemeral=True)


    @app_commands.command(name="clear", description="Clears the entire upcoming queue.")
    async def clear(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel
        q.clear()
        await interaction.response.send_message("🧹 **Queue cleared.**")

        # Start idle timer when /clear command used
        bot_voice = interaction.guild.voice_client
        voice_events_cog = self.bot.get_cog("VoiceEvents")
        if voice_events_cog and bot_voice:
            voice_events_cog.start_idle_timer(interaction.guild_id, bot_voice)

        # Broadcast queue updated to Web clients
        try:
            from app.core.ws_manager import ws_manager, get_player_state_data
            state_data = get_player_state_data(str(interaction.guild_id), self.bot)
            await ws_manager.broadcast(interaction.guild_id, {
                "event": "queue_updated",
                "guild_id": str(interaction.guild_id),
                "data": state_data
            })
        except ImportError:
            pass


    @app_commands.command(name="disconnect", description="Disconnects the bot from the voice channel.")
    async def disconnect(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        bot_voice = interaction.guild.voice_client
        if bot_voice:
            q.clear()
            q.pending_next_song = None
            await update_presence(self.bot, None)
            await bot_voice.disconnect()
            await interaction.response.send_message("👋 **Disconnected from the voice channel.**")
        else:
            await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)


    @app_commands.command(name="help", description="Shows all available music commands.")
    async def help_command(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel

        embed = discord.Embed(
            title="🎶 Music Bot Commands",
            description="Supports: 🔴 YouTube | 🟢 Spotify | 🟠 SoundCloud",
            color=COLORS['default']
        )
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            
        embed.add_field(
            name="🎵 Playback",
            value=(
                "`/play` | `e!play [query/url]` — Play from YouTube, Spotify, SoundCloud\n"
                "`/pause` | `e!pause` — Pause current song\n"
                "`/resume` | `e!resume` — Resume paused song\n"
                "`/stop` | `e!stop` — Stop and clear queue\n"
                "`/nowplaying` | `e!np` — Show current song"
            ),
            inline=False
        )
        embed.add_field(
            name="⏭️ Queue",
            value=(
                "`/skip` | `e!skip` — Skip to next song\n"
                "`/previous` | `e!previous` — Go back to previous song\n"
                "`/queue` | `e!queue` — Show queue list\n"
                "`/remove` | `e!remove [index]` — Remove song from queue\n"
                "`/clear` | `e!clear` — Clear entire queue\n"
                "`/shuffle` | `e!shuffle` — Shuffle queue"
            ),
            inline=False
        )
        embed.add_field(
            name="⚙️ Settings",
            value=(
                "`/volume` | `e!volume [0-100]` — Set volume\n"
                "`/loop` | `e!loop [off/song/queue]` — Set loop mode\n"
                "`/disconnect` | `e!dc` — Disconnect bot"
            ),
            inline=False
        )
        embed.set_footer(text="Use /help or e!help anytime")
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="lyrics", description="Shows the lyrics of the current song or a searched song.")
    @app_commands.describe(query="The song title to search for (optional).")
    async def lyrics(self, interaction: discord.Interaction, query: Optional[str] = None):
        await interaction.response.defer()
        
        q = self.get_queue(interaction.guild_id)
        q.last_channel = interaction.channel
        
        search_title = ""
        search_artist = ""
        
        if query:
            search_title = query
        else:
            if not q.now_playing:
                return await interaction.followup.send(
                    embed=create_error_embed("❌ No song is currently playing. Use /lyrics [song title] instead.")
                )
            search_title = q.now_playing.title
            search_artist = getattr(q.now_playing, 'artist', '')
            
        try:
            song_info = await self.bot.loop.run_in_executor(
                None, self.lyrics.get_lyrics, search_title, search_artist
            )
        except LyricsServiceError:
            return await interaction.followup.send(
                embed=create_error_embed("❌ Lyrics service unavailable, try again later")
            )
            
        if not song_info or not song_info.get("lyrics"):
            return await interaction.followup.send(
                embed=create_error_embed(f"❌ Lyrics not found for {query or search_title}")
            )
            
        # Paginate lyrics
        pages = LyricsView.paginate_lyrics(song_info["lyrics"])
        
        view = LyricsView(
            title=song_info["title"],
            artist=song_info["artist"],
            pages=pages,
            url=song_info["url"],
            thumbnail=song_info["thumbnail"]
        )
        
        if len(pages) == 1:
            await interaction.followup.send(embed=view.generate_embed())
        else:
            await interaction.followup.send(embed=view.generate_embed(), view=view)

# Required setup function for cogs
async def setup(bot):
    await bot.add_cog(Music(bot))
