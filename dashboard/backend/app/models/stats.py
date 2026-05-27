from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from app.models.base import Base

class PlaybackHistory(Base):
    __tablename__ = "playback_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guild_id = Column(String(64), index=True, nullable=False)
    song_title = Column(String(256), nullable=False)
    song_url = Column(String(512), nullable=False)
    platform = Column(String(32), nullable=False)
    duration = Column(Integer, nullable=False)  # In seconds
    requester_id = Column(String(64), nullable=False)
    played_at = Column(DateTime, default=datetime.utcnow, index=True)
