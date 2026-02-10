import pytest
from fastapi import status
from tests import data_mandatory_fields, data_all_fields
import uuid

@pytest.mark.parametrize("data_module, label", [
    (data_mandatory_fields, "mandatory_fields"),
    (data_all_fields, "all_fields")
])
def test_add_inventory_item_parameterized(client, auth_headers, data_module, label):
    """Scenario: Add inventory item with both mandatory and all fields."""
    data = data_module.INVENTORY_DATA.copy()
    # Unique SKU for "all fields" to avoid collision if needed
    if "sku_code" in data and data["sku_code"]:
        data["sku_code"] = f"{data['sku_code']}_{uuid.uuid4().hex[:4]}"
    else:
        # For mandatory if we need to distinguish
        data["name"] = f"{data['name']} {label}"
        
    response = client.post("/api/inventory/", headers=auth_headers, json=data)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_list_inventory(client, auth_headers):
    """Scenario: List inventory."""
    response = client.get("/api/inventory/", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "items" in response.json()

def test_update_inventory_stock(client, auth_headers):
    """Scenario: Update stock levels."""
    # 1. Create item
    data = data_mandatory_fields.INVENTORY_DATA.copy()
    data["name"] = "Update Item"
    create_res = client.post("/api/inventory/", headers=auth_headers, json=data)
    item_id = create_res.json()["item_id"]
    
    # 2. Update
    response = client.put(f"/api/inventory/{item_id}", headers=auth_headers, json={"current_stock": 50})
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]

def test_delete_inventory_item(client, auth_headers):
    """Scenario: Delete an item."""
    # 1. Create item
    data = data_mandatory_fields.INVENTORY_DATA.copy()
    data["name"] = "Delete Item"
    create_res = client.post("/api/inventory/", headers=auth_headers, json=data)
    item_id = create_res.json()["item_id"]
    
    # 2. Delete
    response = client.delete(f"/api/inventory/{item_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "successfully" in response.json()["message"]
