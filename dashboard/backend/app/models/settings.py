from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id = Column(String(64), primary_key=True, index=True)
    dj_role_id = Column(String(64), nullable=True)
    default_volume = Column(Integer, default=50)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    banned_songs = relationship("BannedSongs", back_populates="guild", cascade="all, delete-orphan")


class BannedSongs(Base):
    __tablename__ = "banned_songs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guild_id = Column(String(64), ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), nullable=False)
    query = Column(String(256), nullable=False)
    banned_by = Column(String(64), nullable=False)
    banned_at = Column(DateTime, default=datetime.utcnow)

    guild = relationship("GuildSettings", back_populates="banned_songs")
