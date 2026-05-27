import os
from dotenv import load_dotenv

# Load environment variables from a .env file (if present)
load_dotenv()

class Settings:
    DISCORD_CLIENT_ID: str = os.getenv("DISCORD_CLIENT_ID", "")
    DISCORD_CLIENT_SECRET: str = os.getenv("DISCORD_CLIENT_SECRET", "")
    DISCORD_REDIRECT_URI: str = os.getenv("DISCORD_REDIRECT_URI", "")
    
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change_this_to_a_secure_random_key_in_production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    ADMIN_DISCORD_ID: str = os.getenv("ADMIN_DISCORD_ID", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dashboard.db")

settings = Settings()
