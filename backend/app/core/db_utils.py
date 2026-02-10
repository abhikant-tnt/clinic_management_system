"""Database utility functions for ORM-only operations"""
from sqlalchemy.orm import Session
from contextlib import contextmanager
from app.core.db_session import get_db


@contextmanager
def get_db_session() -> Session:
    """Get a database session with proper transaction management"""
    db = next(get_db())
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# def require_db_session() -> Session:
#     """Get a new database session or raise error if not available"""
#     try:
#         return SessionLocal()
#     except Exception as e:
#         raise RuntimeError(f"Database session not available: {e}")


