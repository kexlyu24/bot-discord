import discord
from typing import Optional

async def update_presence(bot, song: Optional[object] = None, paused: bool = False):
    """Updates the Discord bot's activity presence and status based on playback state."""
    if song is not None:
        if paused:
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name=f"⏸ {song.title}"
            )
            status = discord.Status.do_not_disturb
        else:
            artist = getattr(song, 'artist', '')
            # Truncate if the name is too long for Discord presence (max 128 chars)
            name = f"{song.title} — {artist}" if artist else song.title
            if len(name) > 127:
                name = name[:124] + "..."
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name=name
            )
            status = discord.Status.online
    else:
        activity = discord.Game(name="e!help | /help")
        status = discord.Status.idle

    try:
        await bot.change_presence(activity=activity, status=status)
    except Exception:
        pass
