# Unit Tests

This directory contains unit tests for the clinic management system.

## Running Tests

Run all tests:
```bash
pytest
```

Run tests with verbose output:
```bash
pytest -v
```

Run a specific test file:
```bash
pytest tests/test_utils.py
```

Run a specific test:
```bash
pytest tests/test_utils.py::TestFormatResponse::test_format_response_with_data
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_utils.py` - Tests for common utility functions
- `test_date_helpers.py` - Tests for date helper functions
- `test_auth_services.py` - Tests for authentication services

## Adding New Tests

When adding new functionality, create corresponding test files following the naming convention:
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test functions: `test_<function_name>`

Example:
```python
class TestMyFunction:
    def test_my_function_success(self):
        # Test successful case
        pass
    
    def test_my_function_failure(self):
        # Test failure case
        pass
```

