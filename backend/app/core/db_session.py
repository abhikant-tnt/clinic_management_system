"""SQLAlchemy database session setup"""
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.core.models import Base

# Create database engine using PostgreSQL connection
# This uses the same connection settings as the raw PostgreSQL connection
def build_database_url() -> str:
    """Build PostgreSQL connection URL from settings (URL-encodes special characters)"""
    # URL-encode username and password to handle special characters like @, :, etc.
    user = quote_plus(settings.MAIN_POSTGRES_USER)
    password = quote_plus(settings.MAIN_POSTGRES_PASSWORD) if settings.MAIN_POSTGRES_PASSWORD else ""
    host = settings.MAIN_POSTGRES_HOST
    port = settings.MAIN_POSTGRES_PORT
    database = quote_plus(settings.MAIN_POSTGRES_DB)
    
    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    else:
        return f"postgresql://{user}@{host}:{port}/{database}"

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

