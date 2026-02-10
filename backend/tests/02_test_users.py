import pytest
from fastapi import status
from tests import data_mandatory_fields, data_all_fields
import uuid

@pytest.mark.parametrize("data_module, label", [
    (data_mandatory_fields, "mandatory_fields"),
    (data_all_fields, "all_fields")
])
def test_create_user_parameterized(client, auth_headers, data_module, label):
    """Scenario: Create a user with both mandatory and all fields."""
    data = data_module.USER_DATA.copy()
    # Ensure unique username and phone for each run to avoid 400 Conflict
    unique_id = str(uuid.uuid4())[:8]
    data["username"] = f"{data['username']}_{unique_id}"
    data["phone"] = f"{int(data['phone']) + 1}"[:10] # Tiny hack for unique valid phone
    
    response = client.post("/api/users/", headers=auth_headers, json=data)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_list_users(client, auth_headers):
    """Scenario: List all users."""
    response = client.get("/api/users/", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "users" in response.json()

def test_update_user(client, auth_headers):
    """Scenario: Update a user's details."""
    # 1. Create a user
    data = data_mandatory_fields.USER_DATA.copy()
    data["username"] = f"update_user_{uuid.uuid4().hex[:6]}"
    data["phone"] = "9998887776"
    create_res = client.post("/api/users/", headers=auth_headers, json=data)
    user_id = create_res.json()["user_id"]
    
    # 2. Update the user
    update_data = {"firstname": "Updated", "lastname": "Name"}
    response = client.put(f"/api/users/{user_id}", headers=auth_headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_delete_user(client, auth_headers):
    """Scenario: Delete a user."""
    # 1. Create a user
    data = data_mandatory_fields.USER_DATA.copy()
    data["username"] = f"delete_user_{uuid.uuid4().hex[:6]}"
    data["phone"] = "9998887775"
    create_res = client.post("/api/users/", headers=auth_headers, json=data)
    user_id = create_res.json()["user_id"]
    
    # 2. Delete the user
    response = client.delete(f"/api/users/{user_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]
