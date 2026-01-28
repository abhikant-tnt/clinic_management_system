"""Pytest configuration and shared fixtures"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock
from typing import Generator
from fastapi.testclient import TestClient

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for FastAPI"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_db_session():
    """Mock database session for ORM operations"""
    session = MagicMock()
    session.query.return_value = session
    session.filter.return_value = session
    session.first.return_value = None
    session.all.return_value = []
    session.commit.return_value = None
    session.rollback.return_value = None
    session.close.return_value = None
    return session


@pytest.fixture
def sample_patient_data():
    """Sample patient data for testing"""
    return {
        "firstname": "John",
        "lastname": "Doe",
        "dob": "15/05/1990",
        "age": 34,
        "gender": "male",
        "phone": "1234567890",
        "email": "john.doe@example.com",
        "address1": "123 Main St",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001",
        "emergency_contact_name": "Jane Doe",
        "emergency_contact_phone": "0987654321",
        "referral_source": "walk-in",
        "patient_status": "active",
        "registration_date": "01/01/2024"
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "id": 1,
        "username": "testuser",
        "user_type": "admin",
        "tenant_id": "test-tenant",
        "is_active": True
    }
