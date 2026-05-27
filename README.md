# 🎵 Multi-Platform Discord Music Bot

A production-ready Discord music bot built with Python (`discord.py`), supporting seamless high-quality audio streaming from YouTube, Spotify, SoundCloud, and direct URLs.

## ✨ Features
- 🔴 **YouTube**: Play URLs or search seamlessly.
- 🟢 **Spotify**: Queue single tracks, albums, or up to 100 tracks from a playlist.
- 🟠 **SoundCloud**: Direct audio stream support.
- 🔗 **Direct URLs**: Stream raw `mp3`, `ogg`, `m4a`, `wav` files.
- 🎛️ **Advanced Queue**: Features `/skip`, `/previous`, `/loop`, `/shuffle`, and `/remove`.
- 📊 **Now Playing**: Clean embed showing track thumbnail, requester, and text-based progress bar.
- ⚡ **Resilient Streaming**: Optimized FFmpeg settings to auto-reconnect on network drops.
- 🔐 **Robust Error Handling**: Pre-flight system checks and friendly UI error alerts.
- 🎤 **Lyrics**: `/lyrics` or `e!lyrics [song title]` to get song lyrics (auto-detects current song if no title provided, powered by Genius).

---

## 🛠️ Requirements
- **Python 3.11+**
- **FFmpeg**: Required for audio streaming. Must be in your system's PATH.
- **yt-dlp**: Required for extracting audio streams. Keeps automatically updated via pip.

---

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/bot-discord.git
cd bot-discord
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg
FFmpeg must be installed and added to your system's PATH.
- **Windows**: Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), extract, and add the `bin` folder to your Environment Variables PATH.
- **macOS**: `brew install ffmpeg`
- **Linux (Ubuntu/Debian)**: `sudo apt install ffmpeg`

### 4. Configuration
Rename the `.env.example` file to `.env`:
```bash
cp .env.example .env
```

#### How to get a Discord Bot Token
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** and name your bot.
3. Go to the **Bot** tab on the left menu.
4. Click **Reset Token** and copy the token. **Paste it into `.env` as `DISCORD_TOKEN`.**
5. **Important:** Scroll down and enable **Message Content Intent** and **Server Members Intent**.
6. Go to **OAuth2 -> URL Generator**, check `bot` and `applications.commands`. Give it permissions (Send Messages, Connect, Speak, Embed Links), copy the URL, and invite the bot to your server.

#### How to get Spotify API Credentials
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) and log in.
2. Click **Create app**. Give it a name and description.
3. For "Redirect URI", you can put `http://localhost:8080`.
4. Click **Save** and view your new application.
5. Click **Settings** to find your **Client ID** and **Client Secret**.
6. Paste them into `.env` as `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`.

### 5. Run the Bot
```bash
python main.py
```
*The bot will automatically run a Startup Checker to verify that FFmpeg, yt-dlp, and Spotify are correctly configured!*

---

## 💬 Slash Commands

| Command | Description |
|---|---|
| `/play <query>` | Plays audio from YouTube, Spotify, SC, or search |
| `/pause` | Pauses the current track |
| `/resume` | Resumes a paused track |
| `/stop` | Stops playback and clears the queue |
| `/skip` | Skips the current track |
| `/previous` | Plays the previously played track |
| `/queue` | Displays the current queue (Paginated) |
| `/nowplaying` | Displays current track progress and details |
| `/volume <0-100>` | Adjusts the bot's volume |
| `/loop <off/song/queue>` | Sets the loop mode |
| `/shuffle` | Randomizes the queue |
| `/remove <index>` | Removes a specific track from the queue |
| `/clear` | Clears all upcoming tracks |
| `/disconnect` | Disconnects the bot from the voice channel |
| `/lyrics [song]` | `/lyrics` or `e!lyrics [song title]` — Get song lyrics (auto-detects current song, powered by Genius) |
