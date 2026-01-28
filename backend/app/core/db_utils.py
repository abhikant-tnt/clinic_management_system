"""Database utility functions for ORM-only operations"""
from sqlalchemy.orm import Session
from app.core.db_session import SessionLocal
from contextlib import contextmanager


@contextmanager
def get_db_session() -> Session:
    """Get a database session with proper transaction management"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def require_db_session() -> Session:
    """Get a new database session or raise error if not available"""
    try:
        return SessionLocal()
    except Exception as e:
        raise RuntimeError(f"Database session not available: {e}")


