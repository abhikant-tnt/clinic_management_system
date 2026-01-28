"""
Shared utility functions used across modules
"""
from typing import Any, Dict, List, Set, Optional
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from app.common.schemas import ErrorResponse

def format_response(data: Any, message: str = "Success") -> Dict:
    """Format API response"""
    return {
        "success": True,
        "message": message,
        "data": data
    }

def format_error_response(message: str, errors: Optional[List[str]] = None) -> Dict:
    """Format error response"""
    response = {
        "success": False,
        "message": message
    }
    if errors:
        response["errors"] = errors
    return response

def validate_column_names(column_names: Set[str], allowed_columns: Set[str]) -> Set[str]:
    """
    Validate column names against allowed columns to prevent SQL injection.
    Returns only valid column names.
    Raises ValueError if any column name is not in allowed_columns.
    """
    invalid_columns = column_names - allowed_columns
    if invalid_columns:
        raise ValueError(f"Invalid column names: {', '.join(invalid_columns)}")
    return column_names & allowed_columns

def create_error_response(message: str, status_code: int = 400, errors: Optional[List[str]] = None) -> JSONResponse:
    """
    Create a standardized error response.
    Use this for all error responses to maintain consistency.
    """
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(message=message, errors=errors).model_dump()
    )

def raise_not_found_error(resource: str, resource_id: Any) -> None:
    """
    Raise a standardized 404 Not Found error.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} with ID {resource_id} not found."
    )

def raise_bad_request_error(message: str) -> None:
    """
    Raise a standardized 400 Bad Request error.
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message
    )

def raise_internal_server_error(message: str = "An internal error occurred. Please try again or contact support.") -> None:
    """
    Raise a standardized 500 Internal Server Error.
    """
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message
    )


