"""
Date helper functions for converting between string format (dd/mm/yyyy) and DATE type
"""
from datetime import date, datetime
from typing import Optional


def string_to_date(date_str: str) -> Optional[date]:
    """
    Convert date string from dd/mm/yyyy format to Python date object.
    Returns None if invalid.
    """
    if not date_str:
        return None
    try:
        day, month, year = map(int, date_str.split('/'))
        return date(year, month, day)
    except (ValueError, AttributeError):
        return None


def date_to_string(date_obj: Optional[date]) -> Optional[str]:
    """
    Convert Python date object to dd/mm/yyyy format string.
    Returns None if date_obj is None.
    """
    if not date_obj:
        return None
    if isinstance(date_obj, str):
        return date_obj  # Already a string
    return date_obj.strftime("%d/%m/%Y")


def string_to_datetime(datetime_str: str) -> Optional[datetime]:
    """
    Convert datetime string to Python datetime object.
    Handles various formats.
    """
    if not datetime_str:
        return None
    try:
        # Try dd/mm/yyyy format first
        if '/' in datetime_str:
            day, month, year = map(int, datetime_str.split('/'))
            return datetime(year, month, day)
        # Try ISO format
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None

