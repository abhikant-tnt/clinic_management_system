from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from decimal import Decimal
import uuid
from app.core.config import settings
from app.core.database import local_postgres_conn, local_postgres_cursor, sync_local_to_main
from app.modules.inventory.schemas import InventoryItemCreate, InventoryItemUpdate, InventoryItem

router = APIRouter()

def get_tenant_id() -> str:
    return settings.TENANT_ID

def get_tenant_uuid() -> uuid.UUID:
    """Convert string tenant_id to UUID using deterministic UUID5 generation"""
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # DNS namespace
    return uuid.uuid5(namespace, settings.TENANT_ID)

def convert_date_format(date_str: str) -> str:
    """Convert dd/mm/yyyy to yyyy-mm-dd for PostgreSQL DATE"""
    if not date_str:
        return None
    day, month, year = map(int, date_str.split('/'))
    return f"{year}-{month:02d}-{day:02d}"

def inventory_item_to_dict(item_data) -> dict:
    if isinstance(item_data, dict):
        return item_data
    return {
        "id": str(item_data["id"]) if item_data.get("id") else None,
        "tenant_id": str(item_data["tenant_id"]) if item_data.get("tenant_id") else None,
        "name": item_data["name"],
        "category": item_data["category"],
        "unit": item_data["unit"],
        "current_stock": item_data["current_stock"],
        "min_stock_level": item_data["min_stock_level"],
        "unit_price": float(item_data["unit_price"]) if item_data.get("unit_price") else 0.0,
        "expiry_date": item_data["expiry_date"].isoformat() if isinstance(item_data.get("expiry_date"), datetime.date) else str(item_data.get("expiry_date", "")),
        "supplier_name": item_data["supplier_name"],
        "supplier_phone": item_data["supplier_phone"],
        "created_at": item_data["created_at"].isoformat() if isinstance(item_data.get("created_at"), datetime) else str(item_data.get("created_at", "")),
        "updated_at": item_data["updated_at"].isoformat() if isinstance(item_data.get("updated_at"), datetime) else str(item_data.get("updated_at", ""))
    }

@router.get("/")
def get_inventory_items(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    low_stock: Optional[bool] = None
):
    tenant_id_uuid = get_tenant_uuid()
    sync_local_to_main()
    
    items_list = []
    if local_postgres_cursor:
        try:
            conditions = ["tenant_id = %s"]
            params = [tenant_id_uuid]
            
            if category:
                conditions.append("category = %s")
                params.append(category.lower())
            
            if low_stock:
                conditions.append("current_stock <= min_stock_level")
            
            query = f"""
                SELECT id, tenant_id, name, category, unit, current_stock, min_stock_level,
                       unit_price, expiry_date, supplier_name, supplier_phone,
                       created_at, updated_at
                FROM inventory_items
                WHERE {' AND '.join(conditions)}
                ORDER BY name
            """
            local_postgres_cursor.execute(query, params)
            columns = [desc[0] for desc in local_postgres_cursor.description]
            items_list = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching inventory items: {e}")
    
    total = len(items_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "items": items_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
    }

@router.get("/{item_id}")
def get_inventory_item(item_id: str):
    tenant_id_uuid = get_tenant_uuid()
    
    if local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, tenant_id, name, category, unit, current_stock, min_stock_level,
                       unit_price, expiry_date, supplier_name, supplier_phone,
                       created_at, updated_at
                FROM inventory_items
                WHERE id = %s AND tenant_id = %s
            """, (item_id, tenant_id_uuid))
            record = local_postgres_cursor.fetchone()
            if record:
                columns = [desc[0] for desc in local_postgres_cursor.description]
                return dict(zip(columns, record))
            else:
                raise HTTPException(status_code=404, detail=f"Inventory item with ID {item_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching inventory item: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.post("/")
def create_inventory_item(item_data: InventoryItemCreate):
    tenant_id_uuid = get_tenant_uuid()
    tenant_id_to_use = uuid.UUID(item_data.tenant_id) if item_data.tenant_id else tenant_id_uuid
    
    if local_postgres_cursor and local_postgres_conn:
        try:
            expiry_date_pg = convert_date_format(item_data.expiry_date)
            
            local_postgres_cursor.execute("""
                INSERT INTO inventory_items (
                    tenant_id, name, category, unit, current_stock, min_stock_level,
                    unit_price, expiry_date, supplier_name, supplier_phone, synced_to_main
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                RETURNING id
            """, (
                tenant_id_to_use, item_data.name.lower(), item_data.category.lower(),
                item_data.unit.lower(), item_data.current_stock, item_data.min_stock_level,
                item_data.unit_price, expiry_date_pg, item_data.supplier_name.lower(),
                item_data.supplier_phone
            ))
            
            result = local_postgres_cursor.fetchone()
            item_id = str(result[0]) if result else None
            local_postgres_conn.commit()
            
            if item_id:
                sync_local_to_main()
                return {"message": f"Inventory item created successfully", "item_id": item_id}
            else:
                raise HTTPException(status_code=500, detail="Failed to create inventory item")
                
        except Exception as e:
            local_postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating inventory item: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.put("/{item_id}")
def update_inventory_item(item_id: str, item_data: InventoryItemUpdate):
    tenant_id_uuid = get_tenant_uuid()
    
    if local_postgres_cursor and local_postgres_conn:
        try:
            # Check if item exists
            local_postgres_cursor.execute(
                "SELECT id FROM inventory_items WHERE id = %s AND tenant_id = %s",
                (item_id, tenant_id_uuid)
            )
            if not local_postgres_cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Inventory item with ID {item_id} not found")
            
            update_data = {}
            if item_data.name is not None:
                update_data["name"] = item_data.name.lower()
            if item_data.category is not None:
                update_data["category"] = item_data.category.lower()
            if item_data.unit is not None:
                update_data["unit"] = item_data.unit.lower()
            if item_data.current_stock is not None:
                update_data["current_stock"] = item_data.current_stock
            if item_data.min_stock_level is not None:
                update_data["min_stock_level"] = item_data.min_stock_level
            if item_data.unit_price is not None:
                update_data["unit_price"] = item_data.unit_price
            if item_data.expiry_date is not None:
                update_data["expiry_date"] = convert_date_format(item_data.expiry_date)
            if item_data.supplier_name is not None:
                update_data["supplier_name"] = item_data.supplier_name.lower()
            if item_data.supplier_phone is not None:
                update_data["supplier_phone"] = item_data.supplier_phone
            
            update_data["updated_at"] = datetime.now()
            update_data["synced_to_main"] = False
            
            if not update_data:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            set_clauses = [f"{key} = %s" for key in update_data.keys() if key != "synced_to_main"]
            values = [update_data[key] for key in update_data.keys() if key != "synced_to_main"]
            values.append(item_id)
            values.append(item_id)
            values.append(tenant_id_uuid)
            
            query = f"UPDATE inventory_items SET {', '.join(set_clauses)}, synced_to_main = FALSE WHERE id = %s AND tenant_id = %s"
            local_postgres_cursor.execute(query, values)
            local_postgres_conn.commit()
            
            sync_local_to_main()
            return {"message": f"Inventory item with ID {item_id} updated successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            local_postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error updating inventory item: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.delete("/{item_id}")
def delete_inventory_item(item_id: str):
    tenant_id_uuid = get_tenant_uuid()
    
    if local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute(
                "DELETE FROM inventory_items WHERE id = %s AND tenant_id = %s",
                (item_id, tenant_id_uuid)
            )
            local_postgres_conn.commit()
            
            if local_postgres_cursor.rowcount > 0:
                sync_local_to_main()
                return {"message": f"Inventory item with ID {item_id} deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail=f"Inventory item with ID {item_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            local_postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error deleting inventory item: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.get("/alerts/low-stock")
def get_low_stock_alerts():
    tenant_id_uuid = get_tenant_uuid()
    
    if local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, name, category, current_stock, min_stock_level, unit
                FROM inventory_items
                WHERE tenant_id = %s AND current_stock <= min_stock_level
                ORDER BY (current_stock - min_stock_level) ASC
            """, (tenant_id_uuid,))
            columns = [desc[0] for desc in local_postgres_cursor.description]
            alerts = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
            return {"alerts": alerts, "count": len(alerts)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching low stock alerts: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.get("/alerts/expiring")
def get_expiring_items(days: int = Query(30, ge=1, le=365)):
    tenant_id_uuid = get_tenant_uuid()
    
    if local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, name, category, expiry_date, current_stock, unit
                FROM inventory_items
                WHERE tenant_id = %s AND expiry_date <= CURRENT_DATE + INTERVAL '%s days'
                ORDER BY expiry_date ASC
            """, (tenant_id_uuid, days))
            columns = [desc[0] for desc in local_postgres_cursor.description]
            alerts = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
            return {"alerts": alerts, "count": len(alerts), "days_ahead": days}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching expiring items: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")
