import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

# FFMPEG Options for discord.py VoiceClient
# -reconnect flags help prevent random disconnects from YouTube/Soundcloud streams
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# YTDL Options for extracting info
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

# Bot Colors for standardized Embeds
COLORS = {
    "default": 0x3498db,   # Blue
    "success": 0x2ecc71,   # Green
    "error": 0xe74c3c,     # Red
    "warning": 0xf1c40f,   # Yellow
    "spotify": 0x1DB954,   # Spotify Green
    "youtube": 0xFF0000,   # YouTube Red
    "soundcloud": 0xFF5500 # SoundCloud Orange
}

# Directories and Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "bot.log")
DATA_DIR = os.path.join(BASE_DIR, "data")
COGS_DIR = os.path.join(BASE_DIR, "cogs")
