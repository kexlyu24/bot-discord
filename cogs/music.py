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
from config import COLORS, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from utils.platform_detector import detect_platform
from utils.spotify_handler import SpotifyHandler, SpotifyError
from utils.music_engine import MusicQueue, YTDLSource, Song
from utils.embeds import (
    create_error_embed, create_success_embed, create_now_playing_embed,
    create_queue_embed, create_added_song_embed, create_added_playlist_embed
)

# Global dictionary mapping guild_id -> MusicQueue to keep state per server
queues: Dict[int, MusicQueue] = {}

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
        # We need a reference to the actual queue object for now_playing, 
        # but our view only takes the list. We'll stick to the inline logic we wrote earlier, 
        # or use create_queue_embed if we modify the view to take MusicQueue instead.
        # Let's keep inline for the UI view to prevent circular deps or complexity.
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
            # Acknowledge quietly if they spam previous on page 1
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_pages:
            self.page += 1
            await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        else:
            await interaction.response.defer()


class Music(commands.Cog):
    """Music Cog holding all audio slash commands."""
    def __init__(self, bot):
        self.bot = bot
        self.spotify = SpotifyHandler(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

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
            return # End of queue reached

        asyncio.run_coroutine_threadsafe(self.start_playback(interaction, next_song, q), self.bot.loop)

    async def start_playback(self, interaction: discord.Interaction, song: Song, queue: MusicQueue):
        """Prepares the audio stream and triggers discord voice client."""
        bot_voice = interaction.guild.voice_client
        if not bot_voice:
            return

        try:
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
            
            bot_voice.play(source, after=lambda e: self.play_next(interaction, e))
            
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
        
        if not await self._ensure_voice(interaction):
            return

        bot_voice = interaction.guild.voice_client
        if not bot_voice:
            try:
                bot_voice = await interaction.user.voice.channel.connect()
            except discord.ClientException as e:
                return await interaction.followup.send(f"❌ Could not connect to voice channel: {e}")
        
        q = self.get_queue(interaction.guild_id)
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
                # E.g. "Playlist Name" extraction from URL is complex, so we'll use a placeholder or the query
                await interaction.followup.send(embed=create_added_playlist_embed("Spotify Playlist / Album", query, "spotify", len(added_songs), total_dur))
                
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
        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        if bot_voice and bot_voice.is_playing():
            bot_voice.pause()
            await interaction.response.send_message("⏸️ **Paused the music.**")
        else:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            

    @app_commands.command(name="resume", description="Resumes paused playback.")
    async def resume(self, interaction: discord.Interaction):
        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        if bot_voice and bot_voice.is_paused():
            bot_voice.resume()
            await interaction.response.send_message("▶️ **Resumed the music.**")
        else:
            await interaction.response.send_message("❌ The music is not paused.", ephemeral=True)
            

    @app_commands.command(name="stop", description="Stops playback and clears the queue.")
    async def stop(self, interaction: discord.Interaction):
        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        q = self.get_queue(interaction.guild_id)
        
        q.clear()
        q.pending_next_song = None # Reset overrides
        
        if bot_voice:
            bot_voice.stop()
            
        await interaction.response.send_message("⏹️ **Stopped playback and cleared the queue.**")


    @app_commands.command(name="skip", description="Skips to the next song.")
    async def skip(self, interaction: discord.Interaction):
        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        q = self.get_queue(interaction.guild_id)
        
        # Force skip breaks the song loop explicitly
        next_song = q.skip(force=True)
        q.pending_next_song = next_song
        
        if bot_voice and bot_voice.is_playing():
            bot_voice.stop() # Triggers callback
            await interaction.response.send_message("⏭️ **Skipped.**")
        else:
            await interaction.response.send_message("⏭️ **Skipped.** (Queue advanced manually)")


    @app_commands.command(name="previous", description="Goes back to the previous song.")
    async def previous(self, interaction: discord.Interaction):
        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        q = self.get_queue(interaction.guild_id)
        
        prev_song = q.previous()
        if prev_song:
            q.pending_next_song = prev_song
            if bot_voice and bot_voice.is_playing():
                bot_voice.stop()
            await interaction.response.send_message("⏮️ **Going back to previous song.**")
        else:
            await interaction.response.send_message("❌ No playback history to go back to.", ephemeral=True)


    @app_commands.command(name="queue", description="Shows the current queue.")
    async def queue(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        if q.is_empty:
            return await interaction.response.send_message("📭 The queue is currently empty.")
            
        view = QueueView(list(q.queue))
        await interaction.response.send_message(embed=view.generate_embed(), view=view)

    @app_commands.command(name="nowplaying", description="Shows the currently playing song.")
    async def nowplaying(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        if not q.now_playing:
            return await interaction.response.send_message(embed=create_error_embed("Nothing is currently playing."), ephemeral=True)
            
        await interaction.response.send_message(embed=create_now_playing_embed(q))

    @app_commands.command(name="volume", description="Sets the playback volume (0-100).")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not await self._ensure_voice(interaction): return
        bot_voice = interaction.guild.voice_client
        
        level = max(0, min(100, level))
        if bot_voice and bot_voice.source:
            bot_voice.source.volume = level / 100.0
            await interaction.response.send_message(f"🔊 **Volume set to {level}%.**")
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
        q.loop_mode = mode.value
        await interaction.response.send_message(f"🔁 **Loop mode set to:** {mode.name}")


    @app_commands.command(name="shuffle", description="Shuffles the upcoming queue.")
    async def shuffle(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.shuffle()
        await interaction.response.send_message("🔀 **Queue shuffled!**")


    @app_commands.command(name="remove", description="Removes a song from the queue by its index.")
    async def remove(self, interaction: discord.Interaction, index: int):
        q = self.get_queue(interaction.guild_id)
        song = q.remove(index - 1) 
        if song:
            await interaction.response.send_message(f"🗑️ Removed **{song.title}** from the queue.")
        else:
            await interaction.response.send_message("❌ Invalid queue index.", ephemeral=True)


    @app_commands.command(name="clear", description="Clears the entire upcoming queue.")
    async def clear(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        q.clear()
        await interaction.response.send_message("🧹 **Queue cleared.**")


    @app_commands.command(name="disconnect", description="Disconnects the bot from the voice channel.")
    async def disconnect(self, interaction: discord.Interaction):
        bot_voice = interaction.guild.voice_client
        if bot_voice:
            q = self.get_queue(interaction.guild_id)
            q.clear()
            q.pending_next_song = None
            await bot_voice.disconnect()
            await interaction.response.send_message("👋 **Disconnected from the voice channel.**")
        else:
            await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)

# Required setup function for cogs
async def setup(bot):
    await bot.add_cog(Music(bot))
