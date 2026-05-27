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

## Quick Start

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
pip install -r dashboard/backend/requirements.txt
```

### 2. Install Frontend dependencies
```bash
cd dashboard/frontend
npm install
```

### 3. Configure environment
```bash
cp .env.example .env
cp dashboard/backend/.env.example dashboard/backend/.env
```
Fill in all tokens in both `.env` files.

### 4. Run everything
- **Windows**: double-click `start.bat`
- **Linux/Mac**: `bash start.sh`

### 5. Open dashboard
Visit [http://localhost:3000](http://localhost:3000) in your browser.

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
