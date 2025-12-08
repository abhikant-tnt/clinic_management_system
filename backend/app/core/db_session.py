"""SQLAlchemy database session setup"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.core.models import Base

# Create database engine using local PostgreSQL connection
# This uses the same connection settings as the raw PostgreSQL connection
def build_database_url() -> str:
    """Build PostgreSQL connection URL from settings"""
    password = f":{settings.LOCAL_POSTGRES_PASSWORD}" if settings.LOCAL_POSTGRES_PASSWORD else ""
    return f"postgresql://{settings.LOCAL_POSTGRES_USER}{password}@{settings.LOCAL_POSTGRES_HOST}:{settings.LOCAL_POSTGRES_PORT}/{settings.LOCAL_POSTGRES_DB}"

engine = create_engine(
    build_database_url(),
    pool_pre_ping=True,
    echo=False  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables (creates tables if they don't exist)"""
    Base.metadata.create_all(bind=engine)

