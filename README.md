# 🎵 Eq's Music Bot

## Features
- 🔴 YouTube — URL & search
- 🟢 Spotify — track, album, playlist  
- 🟠 SoundCloud — URL & search
- 🎤 Lyrics via Genius
- 🎮 Interactive player controls (e!np)
- 🔁 Loop (off/song/queue)
- 🔀 Shuffle, volume, queue management
- 💤 Auto-disconnect after 5min idle
- ⌨️ Slash commands + e! prefix

## Requirements
- Python 3.11+
- FFmpeg (add to system PATH)
- yt-dlp
- Spotify Developer credentials
- Genius API token

## Installation
1. Clone the repository
2. pip install -r requirements.txt
3. Copy .env.example to .env and fill in tokens
4. Run: py main.py

## Commands
| Command | Description |
|---------|-------------|
| /play | e!play [query/url] | Play music |
| /pause | e!pause | Pause |
| /resume | e!resume | Resume |
| /stop | e!stop | Stop & clear queue |
| /skip | e!skip | Skip song |
| /previous | e!previous | Previous song |
| /queue | e!queue | Show queue |
| /nowplaying | e!np | Now playing + controls |
| /lyrics | e!lyrics | Get lyrics |
| /volume | e!volume [0-100] | Set volume |
| /loop | e!loop [off/song/queue] | Loop mode |
| /shuffle | e!shuffle | Shuffle queue |
| /remove | e!remove [index] | Remove from queue |
| /clear | e!clear | Clear queue |
| /disconnect | e!dc | Disconnect bot |

## Environment Variables
DISCORD_TOKEN=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
GENIUS_API_TOKEN=

## Getting API Tokens
- Discord: https://discord.com/developers/applications
- Spotify: https://developer.spotify.com/dashboard
- Genius: https://genius.com/api-clients
