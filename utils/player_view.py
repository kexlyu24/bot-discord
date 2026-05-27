import discord
from typing import Optional

class PlayerView(discord.ui.View):
    """Interactive Discord UI View for now playing controls."""
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=120.0)
        self.cog = cog
        self.guild_id = guild_id
        self.message: Optional[discord.Message] = None
        self.update_buttons()

    async def on_timeout(self):
        self.disable_all_buttons()
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    def update_buttons(self):
        q = self.cog.get_queue(self.guild_id)
        guild = self.cog.bot.get_guild(self.guild_id)
        bot_voice = guild.voice_client if guild else None
        
        # ⏮ Previous
        has_history = len(q.history) > 0 if q else False
        self.prev_button.disabled = not has_history
        
        # ⏸/▶ Pause/Resume
        is_paused = bot_voice.is_paused() if bot_voice else False
        self.play_pause_button.label = "▶" if is_paused else "⏸"
        
        # 🔁 Loop
        if q:
            if q.loop_mode == "song":
                self.loop_button.label = "🔁 Song"
                self.loop_button.style = discord.ButtonStyle.green
            elif q.loop_mode == "queue":
                self.loop_button.label = "🔁 Queue"
                self.loop_button.style = discord.ButtonStyle.green
            else:
                self.loop_button.label = "🔁 Off"
                self.loop_button.style = discord.ButtonStyle.grey

    def disable_all_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    async def refresh_message(self, interaction: discord.Interaction):
        q = self.cog.get_queue(self.guild_id)
        from utils.embeds import create_now_playing_embed
        
        if not q.now_playing:
            self.disable_all_buttons()
            embed = discord.Embed(title="❌ Nothing Playing", description="Nothing is currently playing.", color=0xe74c3c)
            await interaction.response.edit_message(embed=embed, view=self)
            return
            
        embed = create_now_playing_embed(q)
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    # Row 1 Buttons
    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.blurple, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.cog.get_queue(self.guild_id)
        bot_voice = interaction.guild.voice_client
        
        prev_song = q.previous()
        if prev_song:
            q.pending_next_song = prev_song
            if bot_voice:
                bot_voice.stop()
            from utils.presence import update_presence
            await update_presence(self.cog.bot, prev_song, paused=False)
            await self.refresh_message(interaction)
        else:
            await interaction.response.send_message("❌ No previous song in history.", ephemeral=True)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.green, row=0)
    async def play_pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_voice = interaction.guild.voice_client
        q = self.cog.get_queue(self.guild_id)
        if not bot_voice:
            return await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)
            
        from utils.presence import update_presence
        if bot_voice.is_playing():
            bot_voice.pause()
            if q.now_playing:
                await update_presence(self.cog.bot, q.now_playing, paused=True)
        elif bot_voice.is_paused():
            bot_voice.resume()
            if q.now_playing:
                await update_presence(self.cog.bot, q.now_playing, paused=False)
                
        await self.refresh_message(interaction)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.red, row=0)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.cog.get_queue(self.guild_id)
        bot_voice = interaction.guild.voice_client
        
        q.clear()
        q.pending_next_song = None
        
        from utils.presence import update_presence
        await update_presence(self.cog.bot, None)
        
        if bot_voice:
            bot_voice.stop()
            
        self.disable_all_buttons()
        embed = discord.Embed(title="⏹ Stopped", description="Playback stopped and queue cleared.", color=0xe74c3c)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.blurple, row=0)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.cog.get_queue(self.guild_id)
        bot_voice = interaction.guild.voice_client
        
        next_song = q.skip(force=True)
        q.pending_next_song = next_song
        
        if bot_voice and bot_voice.is_playing():
            bot_voice.stop()
            
        # Give a small moment for skip to register, then refresh the embed
        await asyncio.sleep(0.5)
        await self.refresh_message(interaction)

    @discord.ui.button(label="🔁 Off", style=discord.ButtonStyle.grey, row=0)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.cog.get_queue(self.guild_id)
        if q.loop_mode == "off":
            q.loop_mode = "song"
        elif q.loop_mode == "song":
            q.loop_mode = "queue"
        else:
            q.loop_mode = "off"
            
        await self.refresh_message(interaction)

    # Row 2 Buttons
    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.grey, row=1)
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.cog.get_queue(self.guild_id)
        if q.is_empty:
            return await interaction.response.send_message("❌ Queue is empty, nothing to shuffle.", ephemeral=True)
        q.shuffle()
        await self.refresh_message(interaction)

    @discord.ui.button(label="Queue", emoji="📋", style=discord.ButtonStyle.grey, row=1)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.cog.get_queue(self.guild_id)
        if q.is_empty:
            return await interaction.response.send_message("📭 The queue is currently empty.", ephemeral=True)
            
        from cogs.music import QueueView
        view = QueueView(list(q.queue))
        embed = view.generate_embed()
        
        self.update_buttons()
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Lyrics", emoji="🎤", style=discord.ButtonStyle.grey, row=1)
    async def lyrics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.cog.get_queue(self.guild_id)
        if not q.now_playing:
            return await interaction.response.send_message("❌ No song is currently playing.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        search_title = q.now_playing.title
        search_artist = getattr(q.now_playing, 'artist', '')
        
        try:
            from utils.lyrics_handler import LyricsServiceError
            song_info = await self.cog.bot.loop.run_in_executor(
                None, self.cog.lyrics.get_lyrics, search_title, search_artist
            )
        except LyricsServiceError:
            return await interaction.followup.send("❌ Lyrics service unavailable, try again later", ephemeral=True)
            
        if not song_info or not song_info.get("lyrics"):
            return await interaction.followup.send(f"❌ Lyrics not found for **{search_title}**", ephemeral=True)
            
        from cogs.music import LyricsView
        pages = LyricsView.paginate_lyrics(song_info["lyrics"])
        view = LyricsView(
            title=song_info["title"],
            artist=song_info["artist"],
            pages=pages,
            url=song_info["url"],
            thumbnail=song_info["thumbnail"]
        )
        
        self.update_buttons()
        await interaction.message.edit(view=self)
        
        if len(pages) == 1:
            await interaction.followup.send(embed=view.generate_embed(), ephemeral=True)
        else:
            await interaction.followup.send(embed=view.generate_embed(), view=view, ephemeral=True)

    @discord.ui.button(label="Vol -", emoji="🔊", style=discord.ButtonStyle.grey, row=1)
    async def vol_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_voice = interaction.guild.voice_client
        if not bot_voice or not bot_voice.source:
            return await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
            
        current_volume = bot_voice.source.volume
        new_volume = max(0.0, current_volume - 0.1)
        bot_voice.source.volume = new_volume
        await self.refresh_message(interaction)

    @discord.ui.button(label="Vol +", emoji="🔊", style=discord.ButtonStyle.grey, row=1)
    async def vol_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_voice = interaction.guild.voice_client
        if not bot_voice or not bot_voice.source:
            return await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
            
        current_volume = bot_voice.source.volume
        new_volume = min(1.0, current_volume + 0.1)
        bot_voice.source.volume = new_volume
        await self.refresh_message(interaction)
