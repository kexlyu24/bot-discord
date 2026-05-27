import discord
from discord.ext import commands
import asyncio
import time
import logging
from typing import Optional

logger = logging.getLogger('discord')

# Import Shared Music State and UI
import cogs.music
from cogs.music import QueueView, LyricsView

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

@commands.guild_only()
class PrefixMusic(commands.Cog):
    """Music commands via the traditional e! prefix."""
    
    def __init__(self, bot):
        self.bot = bot
        self.spotify = SpotifyHandler(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        self.lyrics = LyricsHandler(GENIUS_API_TOKEN)
        
    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in cogs.music.queues:
            cogs.music.queues[guild_id] = MusicQueue()
        return cogs.music.queues[guild_id]

    # ==========================================
    # CORE PLAYBACK ENGINE
    # ==========================================
    def play_next(self, ctx: commands.Context, error=None):
        if error:
            logger.error(f"Player error: {error}")
            
        bot_voice = ctx.guild.voice_client
        if not bot_voice: return
        
        q = self.get_queue(ctx.guild.id)
        
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
                voice_events_cog.start_idle_timer(ctx.guild.id, bot_voice)
            return # End of queue reached

        asyncio.run_coroutine_threadsafe(self.start_playback(ctx, next_song, q), self.bot.loop)

    async def start_playback(self, ctx: commands.Context, song: Song, queue: MusicQueue):
        bot_voice = ctx.guild.voice_client
        if not bot_voice:
            return

        try:
            # Cancel idle timer if a new song starts playing
            voice_events_cog = self.bot.get_cog("VoiceEvents")
            if voice_events_cog:
                voice_events_cog.cancel_idle_timer(ctx.guild.id)

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
            
            bot_voice.play(source, after=lambda e: self.play_next(ctx, e))
            
        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            try:
                from utils.embeds import create_error_embed
                err_msg = f"Skipped **{song.title}**.\nReason: `Age-restricted, unavailable, or deleted.`"
                asyncio.run_coroutine_threadsafe(ctx.send(embed=create_error_embed(err_msg)), self.bot.loop)
            except Exception:
                pass
            self.play_next(ctx) # Skip gracefully if resolving fails

    async def _ensure_voice(self, ctx: commands.Context) -> bool:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=create_error_embed("You must be in a voice channel to use this command."))
            return False
            
        bot_voice = ctx.guild.voice_client
        user_channel = ctx.author.voice.channel
        
        if bot_voice and bot_voice.channel.id != user_channel.id:
            await ctx.send(embed=create_error_embed(f"You must be in the same voice channel as the bot ({bot_voice.channel.mention})."))
            return False
            
        me = ctx.guild.me
        permissions = user_channel.permissions_for(me)
        if not permissions.connect:
            await ctx.send(embed=create_error_embed("I do not have permission to **Connect** to your voice channel."))
            return False
        if not permissions.speak:
            await ctx.send(embed=create_error_embed("I do not have permission to **Speak** in your voice channel."))
            return False
            
        return True

    # ==========================================
    # COMMANDS
    # ==========================================
    
    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str = None):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        # Cancel idle timer when user uses e!play
        voice_events_cog = self.bot.get_cog("VoiceEvents")
        if voice_events_cog:
            voice_events_cog.cancel_idle_timer(ctx.guild.id)

        if not query:
            embed = discord.Embed(
                title="🎵 Play Command Usage",
                description="Use `e!play <URL or Search>`\n\n**Supported:**\n- YouTube (Video/Search)\n- Spotify (Track/Album/Playlist)\n- SoundCloud",
                color=COLORS['default']
            )
            return await ctx.send(embed=embed)
            
        if not await self._ensure_voice(ctx): return
        
        bot_voice = ctx.guild.voice_client
        if not bot_voice:
            bot_voice = await ctx.author.voice.channel.connect()
            
        platform = detect_platform(query)
        added_songs = []
        
        try:
            if platform == "spotify":
                if not self.spotify.sp:
                    return await ctx.send(embed=create_error_embed("Spotify API is not configured! Check your bot's `.env` file."))
                    
                if "track" in query:
                    t = self.spotify.get_track(query)
                    song = Song(t['title'], query, "", t['duration'], t['thumbnail'], ctx.author, "spotify")
                    song.artist = t['artist']
                    added_songs.append(song)
                elif "album" in query:
                    for t in self.spotify.get_album(query):
                        song = Song(t['title'], query, "", t['duration'], t['thumbnail'], ctx.author, "spotify")
                        song.artist = t['artist']
                        added_songs.append(song)
                elif "playlist" in query:
                    status_msg = await ctx.send("⏳ Fetching playlist tracks...")
                    
                    async def progress_cb(current, total):
                        try:
                            if current % 100 == 0 or current == total:
                                await status_msg.edit(content=f"⏳ Loading playlist... {current}/{total} tracks")
                        except Exception:
                            pass
                            
                    tracks = await self.spotify.get_playlist(query, self.bot.loop, progress_cb)
                    
                    for t in tracks:
                        song = Song(t['title'], query, "", t['duration'], t['thumbnail'], ctx.author, "spotify")
                        song.artist = t['artist']
                        added_songs.append(song)
                        
                    if len(tracks) >= 500:
                        await ctx.send("⚠️ **Note:** Playlist capped at 500 tracks to ensure bot stability.")
                        
                    await status_msg.delete()
                else:
                    return await ctx.send(embed=create_error_embed("Unsupported Spotify URL."))
                    
            elif platform == "soundcloud":
                song = YTDLSource.from_soundcloud(query)
                song.requester = ctx.author
                added_songs.append(song)
                
            else:
                if platform == "search":
                    song = await YTDLSource.search_youtube(query, ctx.author, self.bot.loop)
                else:
                    song = await YTDLSource.from_url(query, ctx.author, platform, self.bot.loop)
                added_songs.append(song)
                
            # Enqueueing
            total_dur = 0
            for s in added_songs:
                q.add(s)
                total_dur += s.duration
                
            if len(added_songs) == 1:
                s = added_songs[0]
                position = len(q.queue)
                await ctx.send(embed=create_added_song_embed(s, position))
            else:
                await ctx.send(embed=create_added_playlist_embed("Playlist / Album", query, platform, len(added_songs), total_dur))
                
            if not bot_voice.is_playing() and not bot_voice.is_paused():
                next_s = q.skip()
                if next_s:
                    await self.start_playback(ctx, next_s, q)
                    
        except Exception as e:
            logger.error(f"Error extracting audio: {e}", exc_info=True)
            await ctx.send(embed=create_error_embed(f"Could not load audio: {str(e)[:100]}"))

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        bot_voice = ctx.guild.voice_client
        if bot_voice.is_playing():
            bot_voice.pause()
            if q.now_playing:
                await update_presence(self.bot, q.now_playing, paused=True)
            await ctx.send(embed=create_success_embed("Paused the music. ⏸️"))
        else:
            await ctx.send(embed=create_error_embed("Audio is not playing."))

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        bot_voice = ctx.guild.voice_client
        if bot_voice.is_paused():
            bot_voice.resume()
            if q.now_playing:
                await update_presence(self.bot, q.now_playing, paused=False)
            await ctx.send(embed=create_success_embed("Resumed the music. ▶️"))
        else:
            await ctx.send(embed=create_error_embed("Audio is not paused."))

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        bot_voice = ctx.guild.voice_client
        q.clear()
        q.now_playing = None
        await update_presence(self.bot, None)
        if bot_voice.is_playing() or bot_voice.is_paused():
            bot_voice.stop()
        await ctx.send(embed=create_success_embed("Stopped playback and cleared the queue. 🛑"))

        # Start idle timer when e!stop command used
        voice_events_cog = self.bot.get_cog("VoiceEvents")
        if voice_events_cog and bot_voice:
            voice_events_cog.start_idle_timer(ctx.guild.id, bot_voice)

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        bot_voice = ctx.guild.voice_client
        if bot_voice.is_playing() or bot_voice.is_paused():
            bot_voice.stop()
            await ctx.send(embed=create_success_embed("Skipped the current song. ⏭️"))
        else:
            await ctx.send(embed=create_error_embed("Nothing is playing right now."))

    @commands.command(name="previous", aliases=["prev"])
    async def previous(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        bot_voice = ctx.guild.voice_client
        
        prev_song = q.previous()
        if not prev_song:
            return await ctx.send(embed=create_error_embed("No previous song in history."))
            
        q.pending_next_song = prev_song
        
        if bot_voice.is_playing() or bot_voice.is_paused():
            bot_voice.stop()
        else:
            q.now_playing = prev_song
            await self.start_playback(ctx, prev_song, q)
            
        await ctx.send(embed=create_success_embed("Playing previous song. ⏮️"))

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if q.is_empty:
            return await ctx.send("📭 The queue is currently empty.")
            
        view = QueueView(q.queue)
        await ctx.send(embed=view.generate_embed(), view=view)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not q.now_playing:
            return await ctx.send(embed=create_error_embed("Nothing is currently playing."))
            
        view = PlayerView(self, ctx.guild.id)
        embed = create_now_playing_embed(q)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, level: int):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        bot_voice = ctx.guild.voice_client
        if bot_voice and bot_voice.source:
            if 0 <= level <= 100:
                bot_voice.source.volume = level / 100
                await ctx.send(embed=create_success_embed(f"Volume set to **{level}%** 🔊"))
            else:
                await ctx.send(embed=create_error_embed("Volume must be between 0 and 100."))
        else:
            await ctx.send(embed=create_error_embed("Nothing is playing right now."))

    @commands.command(name="loop")
    async def loop(self, ctx: commands.Context, mode: str):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        mode = mode.lower()
        if mode in ["off", "song", "queue"]:
            q.loop_mode = mode
            icons = {"off": "➡️", "song": "🔂", "queue": "🔁"}
            await ctx.send(embed=create_success_embed(f"Loop mode set to: **{mode.capitalize()}** {icons[mode]}"))
        else:
            await ctx.send(embed=create_error_embed("Invalid loop mode. Use `off`, `song`, or `queue`."))

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        if q.is_empty:
            return await ctx.send(embed=create_error_embed("Queue is empty, nothing to shuffle."))
        q.shuffle()
        await ctx.send(embed=create_success_embed("Queue shuffled! 🔀"))

    @commands.command(name="remove", aliases=["rm"])
    async def remove(self, ctx: commands.Context, index: int):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        removed = q.remove(index - 1)
        if removed:
            await ctx.send(embed=create_success_embed(f"Removed **{removed.title}** from the queue."))
        else:
            await ctx.send(embed=create_error_embed("Invalid queue position."))

    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        q.clear()
        await ctx.send(embed=create_success_embed("Cleared the upcoming queue! 🗑️"))

        # Start idle timer when e!clear command used
        bot_voice = ctx.guild.voice_client
        voice_events_cog = self.bot.get_cog("VoiceEvents")
        if voice_events_cog and bot_voice:
            voice_events_cog.start_idle_timer(ctx.guild.id, bot_voice)

    @commands.command(name="disconnect", aliases=["dc", "leave"])
    async def disconnect(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        if not await self._ensure_voice(ctx): return
        bot_voice = ctx.guild.voice_client
        q.clear()
        await update_presence(self.bot, None)
        if bot_voice:
            await bot_voice.disconnect()
            cogs.music.queues.pop(ctx.guild.id, None)
            await ctx.send(embed=create_success_embed("Disconnected from voice and cleared queue. 👋"))

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

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
        await ctx.send(embed=embed)

    @commands.command(name="lyrics")
    async def lyrics_command(self, ctx: commands.Context, *, query: Optional[str] = None):
        q = self.get_queue(ctx.guild.id)
        q.last_channel = ctx.channel

        async with ctx.typing():
            search_title = ""
            search_artist = ""
            
            if query:
                search_title = query
            else:
                if not q.now_playing:
                    return await ctx.send(
                        embed=create_error_embed("❌ No song is currently playing. Use /lyrics [song title] instead.")
                    )
                search_title = q.now_playing.title
                search_artist = getattr(q.now_playing, 'artist', '')
                
            try:
                song_info = await self.bot.loop.run_in_executor(
                    None, self.lyrics.get_lyrics, search_title, search_artist
                )
            except LyricsServiceError:
                return await ctx.send(
                    embed=create_error_embed("❌ Lyrics service unavailable, try again later")
                )
                
            if not song_info or not song_info.get("lyrics"):
                return await ctx.send(
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
                await ctx.send(embed=view.generate_embed())
            else:
                await ctx.send(embed=view.generate_embed(), view=view)

async def setup(bot):
    await bot.add_cog(PrefixMusic(bot))
