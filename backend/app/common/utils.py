"""
Shared utility functions used across modules
"""
from typing import Any, Dict, List

def format_response(data: Any, message: str = "Success") -> Dict:
    """Format API response"""
    return {
        "success": True,
        "message": message,
        "data": data
    }

def format_error_response(message: str, errors: List[str] = None) -> Dict:
    """Format error response"""
    response = {
        "success": False,
        "message": message
    }
    if errors:
        response["errors"] = errors
    return response


