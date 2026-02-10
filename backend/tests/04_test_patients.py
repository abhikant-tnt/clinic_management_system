import pytest
from fastapi import status
from tests import data_mandatory_fields, data_all_fields
import uuid

@pytest.mark.parametrize("data_module, label", [
    (data_mandatory_fields, "mandatory_fields"),
    (data_all_fields, "all_fields")
])
def test_create_patient_parameterized(client, auth_headers, data_module, label):
    """Scenario: Create a patient with both mandatory and all fields."""
    data = data_module.PATIENT_DATA.copy()
    # Ensure unique phone and email
    unique_id = uuid.uuid4().hex[:6]
    data["phone"] = f"9{uuid.uuid4().int % 10**9:09d}" # Random 10 digit
    if "email" in data:
        data["email"] = f"test_{unique_id}@example.com"
    
    response = client.post("/api/patients/", headers=auth_headers, json=data)
    assert response.status_code == status.HTTP_201_CREATED
    assert "successfully" in response.json()["message"]

def test_list_patients(client, auth_headers):
    """Scenario: List all patients."""
    response = client.get("/api/patients/", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "patients" in response.json()

def test_update_patient(client, auth_headers):
    """Scenario: Update patient details."""
    # 1. Create patient
    data = data_mandatory_fields.PATIENT_DATA.copy()
    data["phone"] = "9876543212"
    data["email"] = "update@test.com"
    create_res = client.post("/api/patients/", headers=auth_headers, json=data)
    patient_id = create_res.json()["patient_id"]
    
    # 2. Update
    update_data = {"address1": "New Address", "status": "checked_in"}
    response = client.put(f"/api/patients/{patient_id}", headers=auth_headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_delete_patient(client, auth_headers):
    """Scenario: Delete a patient."""
    # 1. Create patient
    data = data_mandatory_fields.PATIENT_DATA.copy()
    data["phone"] = "9876543213"
    data["email"] = "delete@test.com"
    create_res = client.post("/api/patients/", headers=auth_headers, json=data)
    patient_id = create_res.json()["patient_id"]
    
    # 2. Delete
    response = client.delete(f"/api/patients/{patient_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_patient_invalid_phone(client, auth_headers):
    """Scenario: Error when phone is not 10 digits."""
    data = data_mandatory_fields.PATIENT_DATA.copy()
    data["phone"] = "123" # Invalid
    
    response = client.post("/api/patients/", headers=auth_headers, json=data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "phone" in str(response.json()["errors"]).lower() or "10" in str(response.json()["errors"])
