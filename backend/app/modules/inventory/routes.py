from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Any
from datetime import datetime, date
import uuid
from app.core.config import settings
from app.core.db_utils import get_db_session
from app.core.models import InventoryItemModel
from app.core.dependencies import get_current_active_user
from app.common.utils import raise_not_found_error, raise_internal_server_error
from sqlalchemy import and_
from app.core.date_helpers import string_to_date
from app.modules.inventory.schemas import InventoryItemCreate, InventoryItemUpdate

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

def inventory_item_to_dict(item_data: Any) -> dict:
    if isinstance(item_data, dict):
        return item_data
    # Handle ORM model object
    return {
        "id": str(item_data.id) if item_data.id else None,
        "tenant_id": str(item_data.tenant_id) if item_data.tenant_id else None,
        "name": item_data.name,
        "category": item_data.category,
        "unit": item_data.unit,
        "current_stock": item_data.current_stock,
        "min_stock_level": item_data.min_stock_level,
        "unit_price": float(item_data.unit_price) if item_data.unit_price else 0.0,
        "expiry_date": item_data.expiry_date.isoformat() if item_data.expiry_date else None,
        "supplier_name": item_data.supplier_name,
        "supplier_phone": item_data.supplier_phone,
        "created_at": item_data.created_at.isoformat() if item_data.created_at else None,
        "updated_at": item_data.updated_at.isoformat() if item_data.updated_at else None
    }

@router.get("/")
async def get_inventory_items(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    low_stock: Optional[bool] = None,
    current_user: dict = Depends(get_current_active_user)
):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        with get_db_session() as session:
            query = session.query(InventoryItemModel).filter(
                InventoryItemModel.tenant_id == tenant_id_str
            )
            
            if category:
                query = query.filter(InventoryItemModel.category == category.lower())
            
            if low_stock:
                query = query.filter(InventoryItemModel.current_stock <= InventoryItemModel.min_stock_level)
            
            items = query.order_by(InventoryItemModel.name).all()
            items_list = [inventory_item_to_dict(item) for item in items]
    except Exception as e:
        raise_internal_server_error(f"Error fetching inventory items: {e}")
    
    total = len(items_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "items": items_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
    }

@router.get("/{item_id}")
async def get_inventory_item(item_id: str, current_user: dict = Depends(get_current_active_user)):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        item_id_int = int(item_id)
        with get_db_session() as session:
            item = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.id == item_id_int,
                    InventoryItemModel.tenant_id == tenant_id_str
                )
            ).first()
            
            if not item:
                raise_not_found_error("Inventory item", item_id)
            
            return inventory_item_to_dict(item)
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID format")
    except Exception as e:
        raise_internal_server_error(f"Error fetching inventory item: {e}")

@router.post("/")
async def create_inventory_item(item_data: InventoryItemCreate, current_user: dict = Depends(get_current_active_user)):
    tenant_id_uuid = get_tenant_uuid()
    tenant_id_to_use = str(uuid.UUID(item_data.tenant_id)) if item_data.tenant_id else str(tenant_id_uuid)
    
    expiry_date_pg = string_to_date(item_data.expiry_date) if item_data.expiry_date else None
    if not expiry_date_pg:
        raise HTTPException(status_code=400, detail="Invalid expiry_date format. Use dd/mm/yyyy")
    
    try:
        with get_db_session() as session:
            new_item = InventoryItemModel(
                tenant_id=tenant_id_to_use,
                name=item_data.name.lower(),
                category=item_data.category.lower(),
                unit=item_data.unit.lower(),
                current_stock=item_data.current_stock,
                min_stock_level=item_data.min_stock_level,
                unit_price=item_data.unit_price,
                expiry_date=expiry_date_pg,
                supplier_name=item_data.supplier_name.lower(),
                supplier_phone=item_data.supplier_phone
            )
            session.add(new_item)
            session.commit()
            session.refresh(new_item)
            
            return {"message": f"Inventory item created successfully", "item_id": str(new_item.id)}
    except Exception as e:
        raise_internal_server_error(f"Error creating inventory item: {e}")

@router.put("/{item_id}")
async def update_inventory_item(item_id: str, item_data: InventoryItemUpdate, current_user: dict = Depends(get_current_active_user)):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        item_id_int = int(item_id)
        with get_db_session() as session:
            item = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.id == item_id_int,
                    InventoryItemModel.tenant_id == tenant_id_str
                )
            ).first()
            
            if not item:
                raise_not_found_error("Inventory item", item_id)
            
            # Update fields
            if item_data.name is not None:
                item.name = item_data.name.lower()
            if item_data.category is not None:
                item.category = item_data.category.lower()
            if item_data.unit is not None:
                item.unit = item_data.unit.lower()
            if item_data.current_stock is not None:
                item.current_stock = item_data.current_stock
            if item_data.min_stock_level is not None:
                item.min_stock_level = item_data.min_stock_level
            if item_data.unit_price is not None:
                item.unit_price = item_data.unit_price
            if item_data.expiry_date is not None:
                expiry_date_pg = string_to_date(item_data.expiry_date)
                if expiry_date_pg:
                    item.expiry_date = expiry_date_pg
            if item_data.supplier_name is not None:
                item.supplier_name = item_data.supplier_name.lower()
            if item_data.supplier_phone is not None:
                item.supplier_phone = item_data.supplier_phone
            
            item.updated_at = datetime.now()
            
            session.commit()
            session.refresh(item)
            
            return {"message": f"Inventory item with ID {item_id} updated successfully"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID format")
    except Exception as e:
        raise_internal_server_error(f"Error updating inventory item: {e}")

@router.delete("/{item_id}")
async def delete_inventory_item(item_id: str, current_user: dict = Depends(get_current_active_user)):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        item_id_int = int(item_id)
        with get_db_session() as session:
            item = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.id == item_id_int,
                    InventoryItemModel.tenant_id == tenant_id_str
                )
            ).first()
            
            if not item:
                raise_not_found_error("Inventory item", item_id)
            
            session.delete(item)
            session.commit()
            
            return {"message": f"Inventory item with ID {item_id} deleted successfully"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID format")
    except Exception as e:
        raise_internal_server_error(f"Error deleting inventory item: {e}")

@router.get("/alerts/low-stock")
async def get_low_stock_alerts(current_user: dict = Depends(get_current_active_user)):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        with get_db_session() as session:
            items = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.tenant_id == tenant_id_str,
                    InventoryItemModel.current_stock <= InventoryItemModel.min_stock_level
                )
            ).order_by((InventoryItemModel.current_stock - InventoryItemModel.min_stock_level).asc()).all()
            
            alerts = [
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "current_stock": item.current_stock,
                    "min_stock_level": item.min_stock_level,
                    "unit": item.unit
                }
                for item in items
            ]
            return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        raise_internal_server_error(f"Error fetching low stock alerts: {e}")

@router.get("/alerts/expiring")
async def get_expiring_items(days: int = Query(30, ge=1, le=365), current_user: dict = Depends(get_current_active_user)):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        from datetime import timedelta
        
        cutoff_date = date.today() + timedelta(days=days)
        
        with get_db_session() as session:
            items = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.tenant_id == tenant_id_str,
                    InventoryItemModel.expiry_date <= cutoff_date
                )
            ).order_by(InventoryItemModel.expiry_date.asc()).all()
            
            alerts = [
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
                    "current_stock": item.current_stock,
                    "unit": item.unit
                }
                for item in items
            ]
            return {"alerts": alerts, "count": len(alerts), "days_ahead": days}
    except Exception as e:
        raise_internal_server_error(f"Error fetching expiring items: {e}")
