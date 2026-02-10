"""Centralized validation utilities"""

def validate_phone_number(v: str) -> str:
    """
    Validate phone number: exactly 10 digits, only digits allowed.
    Raises ValueError with industry standard message for UI.
    """
    v = v.strip() if v else ""
    if not v or not v.isdigit() or len(v) != 10:
        raise ValueError("Please enter correct 10 digit number.")
    return v
