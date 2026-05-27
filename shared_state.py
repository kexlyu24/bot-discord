"""
Shared state module — single source of truth for the queues dictionary.

Both the Discord bot (cogs/) and the dashboard backend (dashboard/backend/)
import `queues` from here, guaranteeing they reference the SAME dict object
in memory when run together via run.py.
"""

from typing import Dict
from utils.music_engine import MusicQueue

# Global dictionary mapping guild_id (int) -> MusicQueue
# This is the ONLY place this dict is created.
queues: Dict[int, MusicQueue] = {}
