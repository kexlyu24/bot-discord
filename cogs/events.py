import discord
from discord.ext import commands
import asyncio
import logging
from typing import Dict

# Import cogs.music so we can safely pop from its queues dictionary
import cogs.music

logger = logging.getLogger('discord')

class VoiceEvents(commands.Cog):
    """Handles automatic voice channel cleanup and memory management."""
    def __init__(self, bot):
        self.bot = bot
        # Maps guild_id to a background timer task for empty voice channel
        self.disconnect_timers: Dict[int, asyncio.Task] = {}
        # Maps guild_id to a background timer task for inactivity (idle)
        self.idle_timers: Dict[int, asyncio.Task] = {}

    async def auto_disconnect_task(self, voice_client: discord.VoiceClient):
        """Timer task that waits 2 minutes then disconnects the bot and cleans memory."""
        try:
            await asyncio.sleep(120)  # Wait 2 minutes
            
            # Re-verify condition: If bot is still connected and channel is still empty
            if voice_client.is_connected():
                humans = [m for m in voice_client.channel.members if not m.bot]
                if not humans:
                    guild_id = voice_client.guild.id
                    
                    # Stop any running playback
                    voice_client.stop()
                    await voice_client.disconnect()
                    
                    # Clean up MusicQueue memory to prevent RAM leaks
                    cogs.music.queues.pop(guild_id, None)
                    
        except asyncio.CancelledError:
            # Timer was successfully cancelled because a user rejoined the channel
            pass

    async def idle_timeout(self, guild_id: int, bot_voice: discord.VoiceClient):
        """Timer task that waits 5 minutes (300s) and disconnects the bot if idle."""
        try:
            await asyncio.sleep(300) # 5 minutes
            
            # Re-check before disconnecting
            if bot_voice and bot_voice.is_connected():
                if not bot_voice.is_playing() and not bot_voice.is_paused():
                    await bot_voice.disconnect()
                    
                    # Get last text channel and pop from queues
                    q = cogs.music.queues.get(guild_id)
                    last_channel = q.last_channel if q else None
                    cogs.music.queues.pop(guild_id, None)
                    
                    if last_channel:
                        try:
                            embed = discord.Embed(
                                description="💤 Left voice channel due to 5 minutes of inactivity.",
                                color=0xf1c40f
                            )
                            await last_channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"Error sending idle notification to channel {last_channel.id}: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up the task from dictionary when it finishes or is cancelled
            if guild_id in self.idle_timers:
                if self.idle_timers[guild_id] == asyncio.current_task():
                    self.idle_timers.pop(guild_id, None)

    def start_idle_timer(self, guild_id: int, bot_voice: discord.VoiceClient):
        """Starts the 5-minute inactivity idle timer for the specified guild."""
        self.cancel_idle_timer(guild_id)
        self.idle_timers[guild_id] = self.bot.loop.create_task(
            self.idle_timeout(guild_id, bot_voice)
        )

    def cancel_idle_timer(self, guild_id: int):
        """Cancels the idle timer for the specified guild if one is active."""
        if guild_id in self.idle_timers:
            self.idle_timers[guild_id].cancel()
            self.idle_timers.pop(guild_id, None)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Monitors voice channels for emptiness or bot force-kicks."""
        bot_voice = member.guild.voice_client
        if not bot_voice:
            return

        guild_id = member.guild.id

        # ==========================================
        # CASE 1: Bot is forcibly disconnected by an admin (or leaves voice)
        # ==========================================
        if member.id == self.bot.user.id and after.channel is None:
            # Cancel empty channel timer if one was running
            if guild_id in self.disconnect_timers:
                self.disconnect_timers[guild_id].cancel()
                del self.disconnect_timers[guild_id]
                
            # Cancel idle timer if one was running
            self.cancel_idle_timer(guild_id)
                
            # Pop the queue to plug the memory leak
            cogs.music.queues.pop(guild_id, None)
            return

        # ==========================================
        # CASE 2: Human members leave or join
        # ==========================================
        humans_in_channel = [m for m in bot_voice.channel.members if not m.bot]

        if len(humans_in_channel) == 0:
            # Channel is completely empty (no humans left) -> Start countdown timer
            if guild_id not in self.disconnect_timers or self.disconnect_timers[guild_id].done():
                self.disconnect_timers[guild_id] = self.bot.loop.create_task(self.auto_disconnect_task(bot_voice))
                
        elif len(humans_in_channel) > 0:
            # A human rejoined the channel -> Cancel the countdown timer
            if guild_id in self.disconnect_timers:
                self.disconnect_timers[guild_id].cancel()
                del self.disconnect_timers[guild_id]

async def setup(bot):
    await bot.add_cog(VoiceEvents(bot))
