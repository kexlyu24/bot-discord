import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import logging
from typing import List, Dict, Optional
import time

logger = logging.getLogger('discord')

import asyncio

class SpotifyError(Exception):
    """Base exception for Spotify handler errors."""
    pass

class SpotifyPrivatePlaylistError(SpotifyError):
    """Raised when a playlist is private or not found."""
    pass

class SpotifyTrackUnavailableError(SpotifyError):
    """Raised when a track is regionally locked or unavailable."""
    pass

class SpotifyHandler:
    def __init__(self, client_id: str, client_secret: str):
        """
        Authenticates with Spotipy using Client Credentials.
        Spotipy's SpotifyClientCredentials automatically handles token caching and refreshing!
        """
        if not client_id or not client_secret:
            logger.warning("Spotify credentials not provided. Spotify links will fail.")
            self.sp = None
            return
            
        auth_manager = SpotifyClientCredentials(
            client_id=client_id, 
            client_secret=client_secret
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        logger.info("Spotify API authenticated successfully.")

    def _retry_api_call(self, func, *args, **kwargs):
        """
        Wrapper to execute Spotify API calls with max 3 retries and full logging.
        Handles rate limits and API instability.
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                logger.info(f"Spotify API Call: {func.__name__} (Attempt {attempt + 1}/{max_attempts})")
                return func(*args, **kwargs)
                
            except spotipy.exceptions.SpotifyException as e:
                logger.error(f"Spotify API Exception on attempt {attempt + 1}: {e}")
                
                # Handle Private Playlist (Usually 404 or 403 error)
                if e.http_status in (403, 404) and "playlist" in str(e).lower():
                    raise SpotifyPrivatePlaylistError("This playlist is private or could not be found.") from e
                    
                # Handle Rate Limiting explicitly (though Spotipy usually does this too)
                if e.http_status == 429:
                    logger.warning("Spotify API Rate Limited! Waiting before retry...")
                    time.sleep(2)
                    continue
                    
                if attempt == max_attempts - 1:
                    raise SpotifyError(f"Failed to fetch data from Spotify: {e.msg}") from e
                
                time.sleep(1) # Backoff before retry
                
            except Exception as e:
                logger.error(f"Unexpected error in Spotify API call: {e}")
                if attempt == max_attempts - 1:
                    raise SpotifyError(f"Unexpected error: {e}") from e
                time.sleep(1)

    def _extract_track_data(self, track_item: dict) -> Optional[Dict]:
        """Parses the raw JSON track data into our standardized dict format."""
        if not track_item or "track" in track_item and not track_item["track"]:
            return None
            
        # Playlists return items inside a "track" key. Albums/Tracks return the data directly.
        track = track_item.get("track", track_item)
        
        # Check if available in region (Spotify doesn't always send this unless market is specified, 
        # but we check it just in case it is present)
        if "is_playable" in track and not track["is_playable"]:
            logger.warning(f"Track '{track.get('name')}' is not playable in the current region.")
            return None

        # Build artist string (e.g., "Artist1, Artist2")
        artists = [artist['name'] for artist in track.get('artists', [])]
        artist_str = ", ".join(artists) if artists else "Unknown Artist"
        
        # Extract the highest resolution thumbnail (the first in the array)
        thumbnail = ""
        album = track.get('album', {})
        if album and album.get('images'):
            thumbnail = album['images'][0]['url']
            
        return {
            "title": track.get('name', 'Unknown Title'),
            "artist": artist_str,
            "duration": track.get('duration_ms', 0) // 1000, # ms to seconds
            "thumbnail": thumbnail,
            "is_local": track.get('is_local', False) # We can't play user's local files on Discord!
        }

    def get_track(self, url: str) -> Dict:
        """Fetches metadata for a single Spotify track."""
        if not self.sp:
            raise SpotifyError("Spotify API is not configured.")
            
        track_info = self._retry_api_call(self.sp.track, url)
        
        if "is_playable" in track_info and not track_info["is_playable"]:
            raise SpotifyTrackUnavailableError("This track is not available in the bot's region.")
            
        data = self._extract_track_data(track_info)
        if not data:
             raise SpotifyTrackUnavailableError("Could not extract track data.")
             
        return data

    def get_album(self, url: str) -> List[Dict]:
        """Fetches metadata for all tracks in a Spotify album."""
        if not self.sp:
            raise SpotifyError("Spotify API is not configured.")
            
        album_info = self._retry_api_call(self.sp.album, url)
        tracks = []
        
        # Album track objects in Spotify API don't include the album art inside the track object.
        # We must grab it from the parent album object.
        album_images = album_info.get('images', [])
            
        for item in album_info['tracks']['items']:
            # Inject album data so _extract_track_data can find the thumbnail
            if 'album' not in item:
                item['album'] = {'images': album_images}
                
            track_data = self._extract_track_data(item)
            
            # Ensure it's valid and not a local file
            if track_data and not track_data.get('is_local'):
                tracks.append(track_data)
                
        return tracks

    async def get_playlist(self, url: str, loop: asyncio.AbstractEventLoop, progress_callback=None) -> List[Dict]:
        """Fetches metadata for tracks in a Spotify playlist (max 500 tracks natively)."""
        if not self.sp:
            raise SpotifyError("Spotify API is not configured.")
            
        tracks = []
        offset = 0
        limit = 100
        max_tracks = 500
        total_expected = None
        
        try:
            while True:
                # Use run_in_executor to prevent blocking Discord's event loop
                playlist_info = await loop.run_in_executor(
                    None,
                    lambda: self._retry_api_call(
                        self.sp.playlist_items, 
                        url, 
                        limit=limit,
                        offset=offset,
                        additional_types=('track',)
                    )
                )
                
                if total_expected is None:
                    total_expected = min(playlist_info['total'], max_tracks)
                    
                for item in playlist_info['items']:
                    track_data = self._extract_track_data(item)
                    
                    # Skip local files which cannot be fetched via YouTube
                    if track_data and not track_data.get('is_local'):
                        tracks.append(track_data)
                        
                    if len(tracks) >= max_tracks:
                        break
                        
                if progress_callback and total_expected > 100:
                    await progress_callback(min(len(tracks), total_expected), total_expected)
                    
                if len(tracks) >= max_tracks or not playlist_info['next']:
                    break
                    
                offset += limit
                
        except Exception as e:
            if len(tracks) > 0:
                logger.warning(f"Spotify API failed mid-pagination: {e}. Salvaging {len(tracks)} tracks.")
                # We use Python closure inspection to cleanly extract the Discord interaction 
                # from the progress_callback without modifying cogs/music.py's method signatures.
                if progress_callback:
                    try:
                        import discord
                        import inspect
                        closure_vars = inspect.getclosurevars(progress_callback).nonlocals
                        interaction = closure_vars.get('interaction')
                        
                        if interaction and hasattr(interaction, 'channel'):
                            embed = discord.Embed(
                                description=f"⚠️ **Spotify API timed out.** Loaded {len(tracks)}/{total_expected or 'Unknown'} tracks from the playlist. Playing what we got!",
                                color=0xf1c40f # Yellow/Orange warning color
                            )
                            # Using the event loop to send the message safely
                            asyncio.run_coroutine_threadsafe(interaction.channel.send(embed=embed), loop)
                    except Exception as hack_err:
                        logger.error(f"Could not send warning embed via closure: {hack_err}")
            else:
                # If we got 0 tracks before failing, nothing to salvage. Raise normally.
                raise e
                
        if not tracks:
            raise SpotifyError("Playlist is empty or only contains unplayable/local tracks.")
            
        return tracks

    def build_search_query(self, track_dict: Dict) -> str:
        """Constructs the search query to be used by yt-dlp."""
        artist = track_dict.get("artist", "")
        title = track_dict.get("title", "")
        return f"{artist} - {title}"
