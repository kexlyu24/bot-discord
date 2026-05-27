import sys
import os
import asyncio
import threading
import uvicorn

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Add backend directory to sys.path to allow imports from "app"
backend_dir = os.path.join(root_dir, "dashboard", "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import Bot and Config
from main import MusicBot
from config import DISCORD_TOKEN

# Import FastAPI instance
from app.main import app

# Initialize MusicBot
bot = MusicBot()

# Attach bot instance to FastAPI app state (Option B: Shared Memory)
app.state.bot = bot

def run_fastapi():
    """Runs the FastAPI backend server."""
    # Uvicorn runs in a separate thread, running its own event loop
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

async def start_bot():
    """Starts the Discord bot connection."""
    try:
        await bot.start(DISCORD_TOKEN)
    except asyncio.CancelledError:
        pass
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("CRITICAL: DISCORD_TOKEN is missing or empty! Please check your .env file.")
        sys.exit(1)

    print("====================================================")
    print("Starting Eq's Music Bot & FastAPI Backend Unified Process...")
    print("====================================================")

    # 1. Start FastAPI in a background daemon thread
    fastapi_thread = threading.Thread(target=run_fastapi, name="FastAPI-Thread", daemon=True)
    fastapi_thread.start()
    print("FastAPI Backend Thread started on http://127.0.0.1:8000")

    # 2. Run the Discord Bot on the main thread's asyncio loop
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\n[Ctrl+C] Received shutdown signal. Cleaning up...")
        # Since uvicorn runs in a daemon thread, it will exit when the main thread exits.
        print("Unified process stopped. Goodbye!")
