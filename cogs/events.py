import discord
from discord.ext import commands
import asyncio
from typing import Dict

# Import cogs.music so we can safely pop from its queues dictionary
import cogs.music

class VoiceEvents(commands.Cog):
    """Handles automatic voice channel cleanup and memory management."""
    def __init__(self, bot):
        self.bot = bot
        # Maps guild_id to a background timer task
        self.disconnect_timers: Dict[int, asyncio.Task] = {}

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

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Monitors voice channels for emptiness or bot force-kicks."""
        bot_voice = member.guild.voice_client
        if not bot_voice:
            return

        guild_id = member.guild.id

        # ==========================================
        # CASE 1: Bot is forcibly disconnected by an admin
        # ==========================================
        if member.id == self.bot.user.id and after.channel is None:
            # Cancel timer if one was running
            if guild_id in self.disconnect_timers:
                self.disconnect_timers[guild_id].cancel()
                del self.disconnect_timers[guild_id]
                
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
