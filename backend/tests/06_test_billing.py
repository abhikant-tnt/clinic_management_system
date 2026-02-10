import pytest
from fastapi import status
from tests import data_mandatory_fields, data_all_fields
from datetime import date
from decimal import Decimal

@pytest.fixture
def billing_setup_ids(client, auth_headers):
    """Setup Patient, Doctor, and Appointment for billing tests."""
    # 1. Patient
    p_data = data_mandatory_fields.PATIENT_DATA.copy()
    p_data["phone"] = "8888888888"
    p_data["email"] = "bill_patient@test.com"
    p_res = client.post("/api/patients/", headers=auth_headers, json=p_data)
    patient_id = p_res.json()["patient_id"]
    
    # 2. Doctor
    d_data = data_mandatory_fields.USER_DATA.copy()
    d_data["username"] = "bill_doctor"
    d_data["phone"] = "8888888880"
    d_data["user_type"] = "doctor"
    d_res = client.post("/api/users/", headers=auth_headers, json=d_data)
    doctor_id = d_res.json()["user_id"]
    
    # 3. Appointment
    today = date.today().strftime("%d/%m/%Y")
    a_data = data_mandatory_fields.APPOINTMENT_DATA.copy()
    a_data.update({
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": today
    })
    a_res = client.post("/api/appointments/", headers=auth_headers, json=a_data)
    # Handle response format variations
    resp_json = a_res.json()
    appt_id = resp_json["appointment"]["id"] if "appointment" in resp_json else resp_json["id"]
    
    return {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appt_id": appt_id
    }

@pytest.mark.parametrize("data_module, label", [
    (data_mandatory_fields, "mandatory_fields"),
    (data_all_fields, "all_fields")
])
def test_create_invoice_parameterized(client, auth_headers, billing_setup_ids, data_module, label):
    """Scenario: Create an invoice with both mandatory and all fields."""
    data = data_module.BILLING_INVOICE_DATA.copy()
    data.update({
        "patient_id": billing_setup_ids["patient_id"],
        "appointment_id": billing_setup_ids["appt_id"],
        "doctor_id": billing_setup_ids["doctor_id"],
        "issue_date": date.today().strftime("%d/%m/%Y"),
        "invoice_number": f"INV-{label[:5].upper()}-{uuid_short()}"
    })
    
    response = client.post("/api/billing/invoices/", headers=auth_headers, json=data)
    assert response.status_code == status.HTTP_201_CREATED
    assert "successfully" in response.json()["message"]

def test_create_walk_in_bill(client, auth_headers):
    """Scenario: Create a walk-in pharmacy bill."""
    data = data_mandatory_fields.BILLING_INVOICE_DATA.copy()
    data.update({
        "customer_name": "Walk-in Customer",
        "issue_date": date.today().strftime("%d/%m/%Y"),
        "invoice_number": f"WALK-{uuid_short()}"
    })
    # Walk-in schema requires item_type to be 'product'
    walkin_payload = {k: v for k, v in data.items() if k not in ["patient_id", "appointment_id", "doctor_id", "purpose"]}
    for item in walkin_payload["items"]:
        item["item_type"] = "product"
    
    response = client.post("/api/billing/pharmacy/walk-in/", headers=auth_headers, json=walkin_payload)
    if response.status_code != status.HTTP_201_CREATED:
        print(f"DEBUG WALK-IN: {response.json()}")
    assert response.status_code == status.HTTP_201_CREATED
    assert "successfully" in response.json()["message"]

def test_billing_math_validation(client, auth_headers):
    """Scenario: Check math validation."""
    today = date.today().strftime("%d/%m/%Y")
    data = {
        "invoice_number": f"ERR-{uuid_short()}",
        "customer_name": "Error User",
        "issue_date": today,
        "total_amount": 1000.0, # Intentional error
        "tax_amount": 10.0,
        "gst_percentage": 5.0,
        "discount_amount": 0.0,
        "adjustments": 0.0,
        "amount_paid": 210.0,
        "status": "paid",
        "items": [
            {"item_type": "product", "description": "Item", "quantity": 1, "unit_price": 200.0, "line_total": 200.0}
        ]
    }
    response = client.post("/api/billing/pharmacy/walk-in/", headers=auth_headers, json=data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Total amount" in str(response.json()["errors"])

def uuid_short():
    import uuid
    return uuid.uuid4().hex[:6]
