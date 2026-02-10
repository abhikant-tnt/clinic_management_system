import pytest
from fastapi import status
from tests import data_mandatory_fields, data_all_fields
from datetime import date

@pytest.fixture
def test_setup_ids(client, auth_headers):
    """Create a patient and a doctor once for appointment tests."""
    # 1. Create Patient
    p_data = data_mandatory_fields.PATIENT_DATA.copy()
    p_data["phone"] = "9999999999"
    p_data["email"] = "appt_patient@test.com"
    p_res = client.post("/api/patients/", headers=auth_headers, json=p_data)
    patient_id = p_res.json()["patient_id"]
    
    # 2. Create Doctor
    d_data = data_mandatory_fields.USER_DATA.copy()
    d_data["username"] = "appt_doctor"
    d_data["phone"] = "9999999990"
    d_data["user_type"] = "doctor"
    d_res = client.post("/api/users/", headers=auth_headers, json=d_data)
    doctor_id = d_res.json()["user_id"]
    
    return {"patient_id": patient_id, "doctor_id": doctor_id}

@pytest.mark.parametrize("data_module, label", [
    (data_mandatory_fields, "mandatory_fields"),
    (data_all_fields, "all_fields")
])
def test_book_appointment_parameterized(client, auth_headers, test_setup_ids, data_module, label):
    """Scenario: Book appointment with both mandatory and all fields."""
    data = data_module.APPOINTMENT_DATA.copy()
    data["patient_id"] = test_setup_ids["patient_id"]
    data["doctor_id"] = test_setup_ids["doctor_id"]
    
    # Ensure date is today or future (mandatory fields has future 2026, but let's be safe)
    data["appointment_date"] = date.today().strftime("%d/%m/%Y")
    if "follow_up_date" in data and data["follow_up_date"]:
        from datetime import timedelta
        data["follow_up_date"] = (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")
    
    response = client.post("/api/appointments/", headers=auth_headers, json=data)
    if response.status_code != status.HTTP_200_OK:
        print(f"DEBUG: {response.json()}")
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_appointment_lifecycle(client, auth_headers, test_setup_ids):
    """Scenario: Complete appointment lifecycle."""
    today = date.today().strftime("%d/%m/%Y")
    data = data_mandatory_fields.APPOINTMENT_DATA.copy()
    data.update({
        "patient_id": test_setup_ids["patient_id"],
        "doctor_id": test_setup_ids["doctor_id"],
        "appointment_date": today
    })
    
    book_res = client.post("/api/appointments/", headers=auth_headers, json=data)
    appt_id = book_res.json()["appointment"]["id"]
    
    response = client.post(f"/api/appointments/{appt_id}/complete", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "completed" in response.json()["message"]

def test_create_prescription(client, auth_headers, test_setup_ids):
    """Scenario: Create prescription for an appointment."""
    today = date.today().strftime("%d/%m/%Y")
    data = data_mandatory_fields.APPOINTMENT_DATA.copy()
    data.update({
        "patient_id": test_setup_ids["patient_id"],
        "doctor_id": test_setup_ids["doctor_id"],
        "appointment_date": today
    })
    
    book_res = client.post("/api/appointments/", headers=auth_headers, json=data)
    appt_id = book_res.json()["appointment"]["id"]
    
    pres_data = {
        "appointment_id": appt_id,
        "description": "Test Prescription",
        "items": [
            {"item_type": "Product", "source": "External", "item_name": "Medicine A", "quantity": "1 bottle"}
        ]
    }
    response = client.post(f"/api/appointments/{appt_id}/prescription", headers=auth_headers, json=pres_data)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]
