"""
Unit tests for common utility functions
"""
import pytest
from fastapi import HTTPException
from app.common.utils import (
    format_response,
    format_error_response,
    validate_column_names,
    create_error_response,
    raise_not_found_error,
    raise_bad_request_error,
    raise_internal_server_error
)


class TestFormatResponse:
    """Tests for format_response function"""
    
    def test_format_response_with_data(self):
        """Test formatting response with data"""
        data = {"id": 1, "name": "Test"}
        result = format_response(data, "Success message")
        
        assert result["success"] is True
        assert result["message"] == "Success message"
        assert result["data"] == data
    
    def test_format_response_default_message(self):
        """Test formatting response with default message"""
        data = {"id": 1}
        result = format_response(data)
        
        assert result["success"] is True
        assert result["message"] == "Success"
        assert result["data"] == data


class TestFormatErrorResponse:
    """Tests for format_error_response function"""
    
    def test_format_error_response_with_message(self):
        """Test formatting error response with message"""
        result = format_error_response("Error occurred")
        
        assert result["success"] is False
        assert result["message"] == "Error occurred"
        assert "errors" not in result
    
    def test_format_error_response_with_errors(self):
        """Test formatting error response with error list"""
        errors = ["Error 1", "Error 2"]
        result = format_error_response("Validation failed", errors)
        
        assert result["success"] is False
        assert result["message"] == "Validation failed"
        assert result["errors"] == errors


class TestValidateColumnNames:
    """Tests for validate_column_names function"""
    
    def test_validate_valid_columns(self):
        """Test validation with valid column names"""
        column_names = {"name", "email", "phone"}
        allowed_columns = {"name", "email", "phone", "address"}
        
        result = validate_column_names(column_names, allowed_columns)
        
        assert result == column_names
    
    def test_validate_invalid_columns(self):
        """Test validation with invalid column names"""
        column_names = {"name", "email", "invalid_column"}
        allowed_columns = {"name", "email", "phone"}
        
        with pytest.raises(ValueError, match="Invalid column names"):
            validate_column_names(column_names, allowed_columns)
    
    def test_validate_partial_match(self):
        """Test validation with some valid and some invalid columns"""
        column_names = {"name", "email", "invalid"}
        allowed_columns = {"name", "email", "phone"}
        
        with pytest.raises(ValueError):
            validate_column_names(column_names, allowed_columns)


class TestErrorResponseHelpers:
    """Tests for error response helper functions"""
    
    def test_create_error_response(self):
        """Test create_error_response function"""
        response = create_error_response("Test error", 400)
        
        assert response.status_code == 400
        content = response.body.decode()
        assert "Test error" in content
    
    def test_raise_not_found_error(self):
        """Test raise_not_found_error function"""
        with pytest.raises(HTTPException) as exc_info:
            raise_not_found_error("Patient", 123)
        
        assert exc_info.value.status_code == 404
        assert "Patient" in exc_info.value.detail
        assert "123" in exc_info.value.detail
    
    def test_raise_bad_request_error(self):
        """Test raise_bad_request_error function"""
        with pytest.raises(HTTPException) as exc_info:
            raise_bad_request_error("Invalid input")
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid input"
    
    def test_raise_internal_server_error(self):
        """Test raise_internal_server_error function"""
        with pytest.raises(HTTPException) as exc_info:
            raise_internal_server_error("Server error")
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Server error"
    
    def test_raise_internal_server_error_default(self):
        """Test raise_internal_server_error with default message"""
        with pytest.raises(HTTPException) as exc_info:
            raise_internal_server_error()
        
        assert exc_info.value.status_code == 500
        assert "internal error" in exc_info.value.detail.lower()

