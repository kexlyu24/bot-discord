import discord
from discord.ext import commands
import logging
import logging.handlers
import os
import asyncio
from config import DISCORD_TOKEN, LOG_FILE, COGS_DIR, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from utils.startup_checker import run_checks

# ==========================================
# 1. LOGGING SETUP
# ==========================================
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(console_handler)

# File Handler (Rotating log file max 5MB, keep 3 backups)
file_handler = logging.handlers.RotatingFileHandler(
    filename=LOG_FILE,
    encoding='utf-8',
    maxBytes=5 * 1024 * 1024,
    backupCount=3
)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(file_handler)


# ==========================================
# 2. BOT CLASS IMPLEMENTATION
# ==========================================
class MusicBot(commands.Bot):
    def __init__(self):
        # Intents required for reading messages and voice states
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None # Disabling default help command as we use app_commands
        )

    async def setup_hook(self):
        """Executed upon startup. Loads cogs and syncs slash commands."""
        logger.info("Setting up cogs...")
        
        # Ensure cogs directory exists
        if not os.path.exists(COGS_DIR):
            os.makedirs(COGS_DIR)
            
        # Load extensions dynamically
        for filename in os.listdir(COGS_DIR):
            if filename.endswith(".py") and not filename.startswith("__"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    logger.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename}: {e}", exc_info=True)

        # Sync app commands to Discord
        logger.info("Syncing slash commands globally...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} slash command(s).")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}", exc_info=True)

        # Register the global error handler
        self.tree.on_error = self.on_app_command_error

    # ==========================================
    # 3. GLOBAL ERROR HANDLER
    # ==========================================
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Global error handler for slash commands."""
        logger.error(f"App command error from {interaction.user}: {error}", exc_info=error)
        
        message = "❌ An unexpected error occurred while processing your command."
        
        # Handle specific error types here if needed
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            message = f"⏳ This command is on cooldown. Try again in {error.retry_after:.2f} seconds."
        elif isinstance(error, discord.app_commands.MissingPermissions):
            message = "🛑 You do not have the required permissions to use this command."
            
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(message, ephemeral=True)
            else:
                await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

    async def on_ready(self):
        logger.info(f"=====================================")
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"discord.py Version: {discord.__version__}")
        logger.info(f"=====================================")
        
        # Set bot presence
        activity = discord.Activity(type=discord.ActivityType.listening, name="music | /play")
        await self.change_presence(activity=activity)

    # ==========================================
    # 4. GRACEFUL SHUTDOWN
    # ==========================================
    async def close(self):
        """Handles graceful shutdown logic (disconnecting voice clients, saving data, etc.)"""
        logger.info("Initiating graceful shutdown...")
        
        # Disconnect all active voice clients to prevent ghost connections
        for vc in self.voice_clients:
            logger.info(f"Disconnecting from voice channel in guild {vc.guild.id}")
            await vc.disconnect(force=True)
            
        logger.info("Closing bot connection to Discord...")
        await super().close()
        logger.info("Bot offline. Goodbye!")


# ==========================================
# 5. ENTRY POINT
# ==========================================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN is missing or empty! Please check your .env file.")
        exit(1)
        
    # Run Dependency and API Checks
    run_checks(DISCORD_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        
    bot = MusicBot()
    
    try:
        # Run the bot, telling discord.py to NOT setup its own logger so it uses ours
        bot.run(DISCORD_TOKEN, log_handler=None)
    except KeyboardInterrupt:
        # KeyboardInterrupt is safely caught by bot.run, which then calls bot.close()
        pass
    except Exception as e:
        logger.critical(f"Fatal error while running bot: {e}", exc_info=True)
