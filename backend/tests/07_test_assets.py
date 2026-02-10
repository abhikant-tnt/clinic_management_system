import pytest
from fastapi import status
from tests import data_mandatory_fields, data_all_fields
import uuid

@pytest.mark.parametrize("data_module, label", [
    (data_mandatory_fields, "mandatory_fields"),
    (data_all_fields, "all_fields")
])
def test_create_room_parameterized(client, auth_headers, data_module, label):
    """Scenario: Create a room with both types of data."""
    data = data_module.ROOM_DATA.copy()
    data["room_number"] = f"{data['room_number']}_{uuid.uuid4().hex[:4]}"
    
    response = client.post("/api/assets/rooms", headers=auth_headers, json=data)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_create_machine_parameterized(client, auth_headers):
    """Scenario: Create a machine attached to a room."""
    # 1. Create room
    room_data = data_mandatory_fields.ROOM_DATA.copy()
    room_data["room_number"] = f"MCH_RM_{uuid.uuid4().hex[:4]}"
    room_res = client.post("/api/assets/rooms", headers=auth_headers, json=room_data)
    room_id = room_res.json()["room_id"]
    
    # 2. Add machines (mandatory then all fields)
    for module in [data_mandatory_fields, data_all_fields]:
        data = module.MACHINE_DATA.copy()
        data["name"] = f"{data['name']}_{uuid.uuid4().hex[:4]}"
        data["room_id"] = room_id
        
        response = client.post("/api/assets/machines", headers=auth_headers, json=data)
        assert response.status_code == status.HTTP_200_OK
        assert "successfully" in response.json()["message"]

def test_list_assets(client, auth_headers):
    """Scenario: List rooms and machines."""
    res_rooms = client.get("/api/assets/rooms", headers=auth_headers)
    assert res_rooms.status_code == status.HTTP_200_OK
    
    res_machines = client.get("/api/assets/machines", headers=auth_headers)
    assert res_machines.status_code == status.HTTP_200_OK
