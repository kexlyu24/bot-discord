from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# SQLAlchemy setup. For SQLite, check_same_thread is set to False to permit multi-threaded async requests.
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
