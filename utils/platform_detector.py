import re

# ==========================================
# REGEX PATTERNS
# ==========================================

# YouTube URLs: matches youtube.com, youtu.be, m.youtube.com, and various paths
YOUTUBE_REGEX = re.compile(r"^(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com|youtu\.be)\/.*", re.IGNORECASE)

# SoundCloud URLs: matches soundcloud.com, snd.sc
SOUNDCLOUD_REGEX = re.compile(r"^(?:https?:\/\/)?(?:www\.|m\.)?(?:soundcloud\.com|snd\.sc)\/.*", re.IGNORECASE)

# Spotify URLs: matches track, album, playlist specifically
SPOTIFY_TRACK_REGEX = re.compile(r"^(?:https?:\/\/)?(?:open\.)?spotify\.com\/track\/[a-zA-Z0-9]+", re.IGNORECASE)
SPOTIFY_ALBUM_REGEX = re.compile(r"^(?:https?:\/\/)?(?:open\.)?spotify\.com\/album\/[a-zA-Z0-9]+", re.IGNORECASE)
SPOTIFY_PLAYLIST_REGEX = re.compile(r"^(?:https?:\/\/)?(?:open\.)?spotify\.com\/playlist\/[a-zA-Z0-9]+", re.IGNORECASE)

# Spotify generic & shortlinks for fallback
SPOTIFY_GENERIC_REGEX = re.compile(r"^(?:https?:\/\/)?(?:open\.)?spotify\.com\/.*", re.IGNORECASE)
SPOTIFY_SHORTLINK_REGEX = re.compile(r"^(?:https?:\/\/)?spotify\.link\/[a-zA-Z0-9]+", re.IGNORECASE)

# Direct Audio File URLs: ends with an audio extension, allowing query parameters ?token=...
DIRECT_URL_REGEX = re.compile(r"^(?:https?:\/\/)?.*\.(mp3|m4a|ogg|wav|flac|webm|aac)(?:[?#].*)?$", re.IGNORECASE)

# Generic URL pattern to distinguish a search query from an actual URL
URL_REGEX = re.compile(r"^(?:https?:\/\/)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(\/.*)?$", re.IGNORECASE)


# ==========================================
# DETECTION FUNCTIONS
# ==========================================

def is_spotify_track(url: str) -> bool:
    """Checks if the URL is a Spotify track."""
    return bool(SPOTIFY_TRACK_REGEX.match(url))

def is_spotify_album(url: str) -> bool:
    """Checks if the URL is a Spotify album."""
    return bool(SPOTIFY_ALBUM_REGEX.match(url))

def is_spotify_playlist(url: str) -> bool:
    """Checks if the URL is a Spotify playlist."""
    return bool(SPOTIFY_PLAYLIST_REGEX.match(url))

def is_soundcloud(url: str) -> bool:
    """Checks if the URL is a SoundCloud link."""
    return bool(SOUNDCLOUD_REGEX.match(url))

def is_youtube(url: str) -> bool:
    """Checks if the URL is a YouTube link (including youtu.be)."""
    return bool(YOUTUBE_REGEX.match(url))

def is_direct_url(url: str) -> bool:
    """Checks if the URL is a direct audio stream."""
    return bool(DIRECT_URL_REGEX.match(url))

def is_url(query: str) -> bool:
    """Checks if the string looks like a valid URL."""
    if query.startswith("http://") or query.startswith("https://"):
        return True
    return bool(URL_REGEX.match(query))

def detect_platform(query: str) -> str:
    """
    Detects the platform from a query string.
    Returns: "spotify", "youtube", "soundcloud", "direct", or "search".
    """
    query = query.strip()
    
    # 1. Spotify Verification
    if (is_spotify_track(query) or 
        is_spotify_album(query) or 
        is_spotify_playlist(query) or 
        bool(SPOTIFY_SHORTLINK_REGEX.match(query)) or 
        bool(SPOTIFY_GENERIC_REGEX.match(query))):
        return "spotify"
        
    # 2. YouTube Verification
    if is_youtube(query):
        return "youtube"
        
    # 3. SoundCloud Verification
    if is_soundcloud(query):
        return "soundcloud"
        
    # 4. Direct Audio File Verification
    if is_direct_url(query):
        return "direct"
        
    # 5. Unknown URLs fallback (let yt-dlp try to extract it)
    if is_url(query):
        return "direct"
        
    # 6. If it's just plain text, treat it as a YouTube search
    return "search"
