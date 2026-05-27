import subprocess
import logging
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import re

logger = logging.getLogger('discord')

def run_checks(discord_token: str, spotify_client_id: str, spotify_client_secret: str) -> bool:
    """
    Runs automated pre-flight checks for system dependencies and API credentials.
    Returns True if critical components passed, False otherwise.
    """
    logger.info("=====================================")
    logger.info("🔍 Running System Pre-Flight Checks...")
    all_passed = True
    
    # 0. Check Discord Token Format
    if not discord_token or len(discord_token) < 50 or "." not in discord_token:
        logger.error("❌ Discord API: Token format is invalid or missing!")
        logger.error("🔧 FIX: Check your DISCORD_TOKEN in the .env file.")
        all_passed = False
    else:
        logger.info("✅ Discord API: Token format appears valid.")

    # 1. Check FFmpeg (Critical)
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        logger.info("✅ FFmpeg: Found and ready.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ FFmpeg: NOT FOUND IN PATH!")
        logger.error("🔧 FIX: Download FFmpeg (https://ffmpeg.org/download.html) and add it to your System PATH environment variables.")
        all_passed = False

    # 2. Check yt-dlp (Critical)
    try:
        version = yt_dlp.version.__version__
        logger.info(f"✅ yt-dlp: Version {version} installed.")
        logger.info("ℹ️ NOTE: yt-dlp updates frequently to bypass YouTube blocks. If streams fail, run: pip install -U yt-dlp")
    except Exception as e:
        logger.error(f"❌ yt-dlp: Error verifying yt-dlp: {e}")
        all_passed = False

    # 3. Check Spotify API (Optional but recommended)
    if spotify_client_id and spotify_client_secret:
        try:
            auth_manager = SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret)
            sp = spotipy.Spotify(auth_manager=auth_manager)
            # Fetch a known track to verify token generation
            sp.track("4cOdK2wGLETKBW3PvgPWqT")
            logger.info("✅ Spotify API: Credentials verified successfully.")
        except Exception as e:
            logger.error(f"❌ Spotify API: Credentials invalid or failed to connect: {e}")
            logger.error("🔧 FIX: Verify your SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in the .env file.")
    else:
        logger.warning("⚠️ Spotify API: Credentials missing.")
        logger.warning("🔧 FIX: Add credentials to your .env file. Spotify links will immediately fail if a user tries to play one.")

    # 4. Check Genius API (Optional)
    import os
    genius_token = os.getenv("GENIUS_API_TOKEN")
    if not genius_token:
        logger.warning("⚠️ Genius API token not set. /lyrics command will be unavailable.")
    else:
        logger.info("✅ Genius API: Token found.")

    logger.info("=====================================")
    return all_passed
