"""
Unit tests for date helper functions
"""
import pytest
from datetime import date, datetime
from app.core.date_helpers import (
    string_to_date,
    date_to_string,
    string_to_datetime
)


class TestStringToDate:
    """Tests for string_to_date function"""
    
    def test_valid_date_string(self):
        """Test conversion of valid date string"""
        result = string_to_date("15/05/1990")
        assert result == date(1990, 5, 15)
    
    def test_invalid_date_string(self):
        """Test conversion of invalid date string"""
        result = string_to_date("invalid")
        assert result is None
    
    def test_empty_string(self):
        """Test conversion of empty string"""
        result = string_to_date("")
        assert result is None
    
    def test_none_input(self):
        """Test conversion of None input"""
        result = string_to_date(None)
        assert result is None
    
    def test_wrong_format(self):
        """Test conversion of wrong format"""
        result = string_to_date("1990-05-15")  # ISO format
        assert result is None
    
    def test_invalid_date_values(self):
        """Test conversion with invalid date values"""
        result = string_to_date("32/13/1990")  # Invalid month and day
        assert result is None


class TestDateToString:
    """Tests for date_to_string function"""
    
    def test_valid_date_object(self):
        """Test conversion of valid date object"""
        test_date = date(1990, 5, 15)
        result = date_to_string(test_date)
        assert result == "15/05/1990"
    
    def test_none_input(self):
        """Test conversion of None input"""
        result = date_to_string(None)
        assert result is None
    
    def test_string_input(self):
        """Test that string input is returned as-is"""
        result = date_to_string("15/05/1990")
        assert result == "15/05/1990"
    
    def test_different_dates(self):
        """Test conversion of different date values"""
        test_cases = [
            (date(2024, 1, 1), "01/01/2024"),
            (date(2024, 12, 31), "31/12/2024"),
            (date(2000, 6, 15), "15/06/2000")
        ]
        
        for test_date, expected in test_cases:
            result = date_to_string(test_date)
            assert result == expected


class TestStringToDatetime:
    """Tests for string_to_datetime function"""
    
    def test_valid_date_string_slash_format(self):
        """Test conversion of valid date string with slash format"""
        result = string_to_datetime("15/05/1990")
        assert result == datetime(1990, 5, 15)
    
    def test_empty_string(self):
        """Test conversion of empty string"""
        result = string_to_datetime("")
        assert result is None
    
    def test_none_input(self):
        """Test conversion of None input"""
        result = string_to_datetime(None)
        assert result is None
    
    def test_invalid_string(self):
        """Test conversion of invalid string"""
        result = string_to_datetime("invalid")
        assert result is None

