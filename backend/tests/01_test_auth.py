import pytest
from fastapi import status

@pytest.fixture
def auth_test_data():
    """Test data for auth tests"""
    return {
        "firstname": "Auth",
        "lastname": "Owner",
        "phone": "1234567890",
        "username": "auth_owner",
        "password": "Password123",
        "user_type": "owner"
    }

def test_register_owner_invalid_password(client, auth_test_data):
    """Scenario: Password missing uppercase/alphabet (as per user request)."""
    data = auth_test_data.copy()
    data["password"] = "12345678"  # Correct length but no alphabet/case
    
    response = client.post("/api/auth/register", json=data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # Pydantic validation error message
    assert "at least one uppercase letter" in str(response.json()["errors"])

def test_register_owner_short_phone(client, auth_test_data):
    """Scenario: Phone number not 10 digits."""
    data = auth_test_data.copy()
    data["phone"] = "123"
    
    response = client.post("/api/auth/register", json=data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "correct 10 digit number" in str(response.json()["errors"]).lower()

def test_register_owner_success(client, auth_test_data):
    """Scenario: Successful owner registration."""
    response = client.post("/api/auth/register", json=auth_test_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["message"] == "Owner registration successful, please login."
    assert "user_id" in response.json()

def test_register_after_owner_exists_fails(client, auth_test_data):
    """Scenario: Attempting registration after owner already exists should fail."""
    # First success
    client.post("/api/auth/register", json=auth_test_data)
    
    # Second attempt (any role)
    data = auth_test_data.copy()
    data["username"] = "another_user"
    data["phone"] = "9000000000"
    data["user_type"] = "doctor"
    
    response = client.post("/api/auth/register", json=data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Registration is closed" in response.json()["detail"]

def test_login_success(client, auth_test_data):
    """Scenario: Successful login with form data."""
    # Ensure owner exists
    client.post("/api/auth/register", json=auth_test_data)
    
    response = client.post(
        "/api/auth/login",
        data={"username": auth_test_data["username"], "password": auth_test_data["password"]}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_wrong_credentials(client, auth_test_data):
    """Scenario: Login with incorrect password."""
    client.post("/api/auth/register", json=auth_test_data)
    
    response = client.post(
        "/api/auth/login",
        data={"username": auth_test_data["username"], "password": "WrongPassword"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect username or password"

def test_get_current_user_profile(client, auth_test_data):
    """Scenario: Access /me with valid token."""
    # Register and login
    client.post("/api/auth/register", json=auth_test_data)
    login_res = client.post(
        "/api/auth/login",
        data={"username": auth_test_data["username"], "password": auth_test_data["password"]}
    )
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == auth_test_data["username"]
    assert response.json()["user_type"] == "owner"

def test_update_profile(client):
    """Scenario: Change password for current user."""
    # 1. Register owner
    owner_data = {
        "firstname": "Profile",
        "lastname": "Owner",
        "phone": "2223334444",
        "username": "profile_owner",
        "password": "Password123",
        "user_type": "owner"
    }
    client.post("/api/auth/register", json=owner_data)
    
    # 2. Login as owner
    owner_login = client.post(
        "/api/auth/login",
        data={"username": owner_data["username"], "password": owner_data["password"]}
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
    
    # 3. Create a staff user
    test_password = "StaffPass123"
    staff_data = {
        "firstname": "Update",
        "lastname": "Test",
        "phone": "9998887776",
        "username": "update_test_user",
        "password": test_password,
        "user_type": "staff"
    }
    client.post("/api/users/", json=staff_data, headers=owner_headers)
    
    # 4. Login as the new staff user
    login_res = client.post(
        "/api/auth/login",
        data={"username": staff_data["username"], "password": staff_data["password"]}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 5. Update password
    new_password = "NewPassword123"
    response = client.put(
        "/api/auth/me",
        headers=headers,
        json={
            "current_password": test_password,
            "new_password": new_password
        }
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Account updated successfully"

def test_delete_own_account(client):
    """Scenario: Self-deletion of a staff account."""
    # 1. Register owner
    owner_data = {
        "firstname": "Delete",
        "lastname": "Owner",
        "phone": "3334445555",
        "username": "delete_owner",
        "password": "Password123",
        "user_type": "owner"
    }
    client.post("/api/auth/register", json=owner_data)
    
    # 2. Login as owner
    owner_login = client.post(
        "/api/auth/login",
        data={"username": owner_data["username"], "password": owner_data["password"]}
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
    
    # 3. Create a staff user
    test_password = "DeletePass123"
    staff_data = {
        "firstname": "To",
        "lastname": "Delete",
        "phone": "9990001112",
        "username": "delete_me_user",
        "password": test_password,
        "user_type": "staff"
    }
    client.post("/api/users/", json=staff_data, headers=owner_headers)
    
    # 4. Login as the new staff user
    login_res = client.post(
        "/api/auth/login",
        data={"username": staff_data["username"], "password": staff_data["password"]}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 5. Delete the account
    response = client.request(
        "DELETE",
        "/api/auth/me",
        headers=headers,
        json={"password": test_password}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Account deleted successfully"
