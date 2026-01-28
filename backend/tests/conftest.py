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


@pytest.fixture
def sample_appointment_data():
    """Sample appointment data for testing (new schema) - appointment_date and appointment_time are required"""
    return {
        "patient_id": 1,
        "doctor_id": 1,
        "appointment_date": "15/01/2024",  # dd/mm/yyyy format (required)
        "appointment_time": "10:00 AM",  # Required - formats: "2.00 pm", "9.00 am", or "14:30"
        "status": "Scheduled",
        "purpose": "Schedule",
        "interval": "30 minutes",
        "payment": "Pending",
        "follow_up_date": None
    }


@pytest.fixture
def sample_billing_invoice_data():
    """Sample billing invoice data for testing (new schema)"""
    return {
        "invoice_number": "INV-2024-001",
        "patient_id": 1,
        "appointment_id": 1,
        "doctor_id": 1,
        "issue_date": "15/01/2024",  # dd/mm/yyyy format
        "purpose": "Consultation",
        "total_amount": 500.00,
        "tax_amount": 50.00,
        "gst_percentage": 10.0,
        "discount_amount": 0.00,
        "coupon_code": None,
        "adjustments": 0.00,
        "amount_paid": 0.00,
        "payment_mode": "Cash",
        "status": "Pending",
        "visit_charge": 300.00,
        "medication_charge": 200.00,
        "is_waived": False,
        "created_by": 1,
        "items": []
    }


@pytest.fixture
def sample_billing_item_data():
    """Sample billing item data for testing"""
    return {
        "item_type": "product",  # Valid values: "service" or "product"
        "description": "Paracetamol 500mg",
        "quantity": 2,
        "unit_price": 25.00,
        "line_total": 50.00,
        "inventory_item_id": None
    }


@pytest.fixture
def sample_staff_data():
    """Sample staff/doctor data for testing"""
    return {
        "firstname": "Dr. Jane",
        "lastname": "Smith",
        "username": "jane.smith",
        "email": "jane.smith@clinic.com",
        "phone": "9876543210",
        "user_type": "doctor",
        "speciality": "General Medicine",
        "is_active": True
    }