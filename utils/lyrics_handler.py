import lyricsgenius
import re
import logging
from typing import Optional

logger = logging.getLogger('discord')

class LyricsServiceError(Exception):
    """Custom exception raised when the Genius API service is down or unconfigured."""
    pass

class LyricsHandler:
    """Handles Genius API interactions for fetching song lyrics."""

    def __init__(self, token: str):
        if not token:
            self.genius = None
            return
        self.genius = lyricsgenius.Genius(token, timeout=10, retries=2)
        # Skip non-songs (e.g. interviews)
        self.genius.skip_non_songs = True
        # Exclude songs with these terms
        self.genius.excluded_terms = ["(Remix)", "(Live)", "(Instrumental)"]

    def clean_lyrics(self, raw: str) -> str:
        """Remove bracketed section tags like [Verse], [Chorus], etc. and Genius junk."""
        if not raw:
            return ""
            
        # Split lines
        lines = raw.split('\n')
        
        # Remove first line if it contains "Lyrics" (Genius starts with "[Track Name] Lyrics")
        if lines and "lyrics" in lines[0].lower():
            lines.pop(0)
            
        text = '\n'.join(lines)
        
        # Remove bracketed section tags like [Verse 1], [Chorus], etc.
        text = re.sub(r'\[.*?\]', '', text)
        
        # Remove Genius-added "Embed" and digits at the very end of the text (e.g., "15Embed")
        text = re.sub(r'\d*Embed$', '', text, flags=re.IGNORECASE)
        
        # Normalize multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def get_lyrics(self, title: str, artist: str = "") -> Optional[dict]:
        """Search Genius for a song and return formatted lyrics data.

        Returns:
            dict with keys: title, artist, lyrics, url, thumbnail
            or None if not found.
        """
        if not self.genius:
            raise LyricsServiceError("Genius API token not configured.")

        try:
            song = self.genius.search_song(title, artist)
        except Exception as e:
            logger.error(f"Genius API error: {e}")
            raise LyricsServiceError("Genius API request failed.")

        if not song:
            return None

        lyrics = song.lyrics or ""
        cleaned_lyrics = self.clean_lyrics(lyrics)

        return {
            "title": song.title,
            "artist": song.artist,
            "lyrics": cleaned_lyrics,
            "url": song.url,
            "thumbnail": song.song_art_image_url if hasattr(song, 'song_art_image_url') else None,
        }
