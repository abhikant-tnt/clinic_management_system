from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Any
from datetime import datetime, date
import uuid
from app.core.config import settings
from app.core.db_utils import get_db_session
from app.modules.inventory.models import InventoryItemModel
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
    """Convert inventory item to dictionary for API response (table view)"""
    if isinstance(item_data, dict):
        return item_data
    # Handle ORM model object
    # Calculate status if not set
    status = None
    if hasattr(item_data, 'status') and item_data.status:
        status = item_data.status
    else:
        # Auto-calculate status based on stock levels and expiry
        from datetime import date, timedelta
        if hasattr(item_data, 'current_stock') and item_data.current_stock <= 0:
            status = "Out of Stock"
        elif hasattr(item_data, 'expiry_date') and item_data.expiry_date:
            days_until_expiry = (item_data.expiry_date - date.today()).days
            if days_until_expiry <= 30 and days_until_expiry >= 0:
                status = "Expiring Soon"
            elif days_until_expiry < 0:
                status = "Expired"
            else:
                status = "Normal"
        else:
            status = "Normal"
    
    return {
        "id": str(item_data.id) if item_data.id else None,
        "tenant_id": str(item_data.tenant_id) if item_data.tenant_id else None,
        # Basic Information
        "name": item_data.name,  # Stock Name
        "product_type": getattr(item_data, 'product_type', None),  # Type
        "category": item_data.category,  # Category
        "sku_code": getattr(item_data, 'sku_code', None),  # Item Code / SKU
        "brand_name": getattr(item_data, 'brand_name', None),  # Brand Name
        "manufacturer": getattr(item_data, 'manufacturer', None),  # Manufacturer
        "description": getattr(item_data, 'description', None),  # Description
        # Stock Configuration
        "unit": item_data.unit,  # Unit
        "pack_size": getattr(item_data, 'pack_size', None),  # Pack Size
        "current_stock": item_data.current_stock,  # Stock Available
        "min_stock_level": item_data.min_stock_level,  # Minimum low-stock alert
        "storage_location": getattr(item_data, 'storage_location', None),  # Storage Location
        "unit_price": float(item_data.unit_price) if item_data.unit_price else 0.0,
        # Batch and Expiry
        "batch_number": getattr(item_data, 'batch_number', None),  # Batch Number
        "expiry_date": item_data.expiry_date.isoformat() if hasattr(item_data, 'expiry_date') and item_data.expiry_date else None,  # Expiry Date
        "status": status,  # Status (Out of Stock, Expiring Soon, Normal)
        # Supplier Information
        "supplier_name": item_data.supplier_name,
        "supplier_phone": item_data.supplier_phone,
        "is_in_stock": item_data.is_in_stock if hasattr(item_data, 'is_in_stock') else (item_data.current_stock > 0),
        # Consumable-Specific Fields
        "is_sterile": getattr(item_data, 'is_sterile', None),
        "is_single_use": getattr(item_data, 'is_single_use', None),
        "is_reusable": getattr(item_data, 'is_reusable', None),
        "expiry_tracking_required": getattr(item_data, 'expiry_tracking_required', None),
        # Pharmaceutical-Specific Fields
        "dosage_strength": getattr(item_data, 'dosage_strength', None),
        "dosage_form": getattr(item_data, 'dosage_form', None),
        "route": getattr(item_data, 'route', None),
        "schedule_type": getattr(item_data, 'schedule_type', None),
        "prescription_required": getattr(item_data, 'prescription_required', None),
        # Timestamps
        "created_at": item_data.created_at.isoformat() if item_data.created_at else None,
        "updated_at": item_data.updated_at.isoformat() if item_data.updated_at else None  # Last Updated
    }

@router.get("/")
async def get_inventory_items(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
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
    """Create a new inventory item (CREATE SKU endpoint with Save button)"""
    tenant_id_uuid = get_tenant_uuid()
    tenant_id_to_use = str(uuid.UUID(item_data.tenant_id)) if item_data.tenant_id else str(tenant_id_uuid)
    
    expiry_date_pg = string_to_date(item_data.expiry_date) if item_data.expiry_date else None
    if item_data.expiry_date and not expiry_date_pg:
        raise HTTPException(status_code=400, detail="Invalid expiry_date format. Use dd/mm/yyyy")
    
    try:
        with get_db_session() as session:
            # Auto-calculate is_in_stock if not provided
            is_in_stock_value = item_data.is_in_stock if item_data.is_in_stock is not None else (item_data.current_stock > 0)
            
            # Calculate status based on stock and expiry
            status_value = item_data.status
            if not status_value:
                from datetime import date, timedelta
                if item_data.current_stock <= 0:
                    status_value = "Out of Stock"
                elif expiry_date_pg:
                    days_until_expiry = (expiry_date_pg - date.today()).days
                    if days_until_expiry <= 30 and days_until_expiry >= 0:
                        status_value = "Expiring Soon"
                    elif days_until_expiry < 0:
                        status_value = "Expired"
                    else:
                        status_value = "Normal"
                else:
                    status_value = "Normal"
            
            new_item = InventoryItemModel(
                tenant_id=tenant_id_to_use,
                # Basic Information
                name=item_data.name.lower() if item_data.name else None,
                product_type=item_data.product_type.lower() if item_data.product_type else None,
                category=item_data.category.lower() if item_data.category else None,
                sku_code=item_data.sku_code.upper() if item_data.sku_code else None,  # SKU codes are usually uppercase
                brand_name=item_data.brand_name.lower() if item_data.brand_name else None,
                manufacturer=item_data.manufacturer.lower() if item_data.manufacturer else None,
                description=item_data.description if item_data.description else None,
                # Stock Configuration
                unit=item_data.unit.lower() if item_data.unit else None,
                pack_size=item_data.pack_size,
                current_stock=item_data.current_stock,
                min_stock_level=item_data.min_stock_level,
                storage_location=item_data.storage_location.lower() if item_data.storage_location else None,
                unit_price=item_data.unit_price,
                # Batch and Expiry
                batch_number=item_data.batch_number.upper() if item_data.batch_number else None,  # Batch numbers are usually uppercase
                expiry_date=expiry_date_pg,
                status=status_value,
                # Supplier Information
                supplier_name=item_data.supplier_name.lower() if item_data.supplier_name else None,
                supplier_phone=item_data.supplier_phone,
                is_in_stock=is_in_stock_value,
                # Consumable-Specific Fields
                is_sterile=item_data.is_sterile,
                is_single_use=item_data.is_single_use,
                is_reusable=item_data.is_reusable,
                expiry_tracking_required=item_data.expiry_tracking_required,
                # Pharmaceutical-Specific Fields
                dosage_strength=item_data.dosage_strength if item_data.dosage_strength else None,
                dosage_form=item_data.dosage_form.lower() if item_data.dosage_form else None,
                route=item_data.route.lower() if item_data.route else None,
                schedule_type=item_data.schedule_type.upper() if item_data.schedule_type else None,
                prescription_required=item_data.prescription_required
            )
            session.add(new_item)
            session.commit()
            session.refresh(new_item)
            
            return {"message": f"Inventory item (SKU) created successfully", "item_id": new_item.id}
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
            
            # Update fields - Basic Information
            if item_data.name is not None:
                item.name = item_data.name.lower()
            if item_data.product_type is not None:
                item.product_type = item_data.product_type.lower()
            if item_data.category is not None:
                item.category = item_data.category.lower()
            if item_data.sku_code is not None:
                item.sku_code = item_data.sku_code.upper()
            if item_data.brand_name is not None:
                item.brand_name = item_data.brand_name.lower()
            if item_data.manufacturer is not None:
                item.manufacturer = item_data.manufacturer.lower()
            if item_data.description is not None:
                item.description = item_data.description
            
            # Stock Configuration
            if item_data.unit is not None:
                item.unit = item_data.unit.lower()
            if item_data.pack_size is not None:
                item.pack_size = item_data.pack_size
            if item_data.current_stock is not None:
                item.current_stock = item_data.current_stock
                # Auto-update is_in_stock if current_stock changes
                if item_data.is_in_stock is None:
                    item.is_in_stock = item_data.current_stock > 0
            if item_data.min_stock_level is not None:
                item.min_stock_level = item_data.min_stock_level
            if item_data.storage_location is not None:
                item.storage_location = item_data.storage_location.lower()
            if item_data.unit_price is not None:
                item.unit_price = item_data.unit_price
            
            # Batch and Expiry
            if item_data.batch_number is not None:
                item.batch_number = item_data.batch_number.upper()
            if item_data.expiry_date is not None:
                expiry_date_pg = string_to_date(item_data.expiry_date)
                if expiry_date_pg:
                    item.expiry_date = expiry_date_pg
            if item_data.status is not None:
                item.status = item_data.status
            else:
                # Auto-calculate status if not provided
                from datetime import date
                if item_data.current_stock is not None:
                    if item_data.current_stock <= 0:
                        item.status = "Out of Stock"
                    elif item.expiry_date:
                        days_until_expiry = (item.expiry_date - date.today()).days
                        if days_until_expiry <= 30 and days_until_expiry >= 0:
                            item.status = "Expiring Soon"
                        elif days_until_expiry < 0:
                            item.status = "Expired"
                        else:
                            item.status = "Normal"
                    else:
                        item.status = "Normal"
            
            # Supplier Information
            if item_data.supplier_name is not None:
                item.supplier_name = item_data.supplier_name.lower()
            if item_data.supplier_phone is not None:
                item.supplier_phone = item_data.supplier_phone
            if item_data.is_in_stock is not None:
                item.is_in_stock = item_data.is_in_stock
            
            # Consumable-Specific Fields
            if item_data.is_sterile is not None:
                item.is_sterile = item_data.is_sterile
            if item_data.is_single_use is not None:
                item.is_single_use = item_data.is_single_use
            if item_data.is_reusable is not None:
                item.is_reusable = item_data.is_reusable
            if item_data.expiry_tracking_required is not None:
                item.expiry_tracking_required = item_data.expiry_tracking_required
            
            # Pharmaceutical-Specific Fields
            if item_data.dosage_strength is not None:
                item.dosage_strength = item_data.dosage_strength
            if item_data.dosage_form is not None:
                item.dosage_form = item_data.dosage_form.lower()
            if item_data.route is not None:
                item.route = item_data.route.lower()
            if item_data.schedule_type is not None:
                item.schedule_type = item_data.schedule_type.upper()
            if item_data.prescription_required is not None:
                item.prescription_required = item_data.prescription_required
            
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
async def get_low_stock_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(get_current_active_user)
):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        with get_db_session() as session:
            query = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.tenant_id == tenant_id_str,
                    InventoryItemModel.current_stock <= InventoryItemModel.min_stock_level
                )
            )
            
            # Get total count for pagination
            total = query.count()
            
            # Apply pagination
            items = query.order_by((InventoryItemModel.current_stock - InventoryItemModel.min_stock_level).asc()).offset((page - 1) * limit).limit(limit).all()
            
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
            
            total_pages = (total + limit - 1) // limit if total > 0 else 1
            
            return {
                "alerts": alerts,
                "count": total,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
    except Exception as e:
        raise_internal_server_error(f"Error fetching low stock alerts: {e}")

@router.get("/alerts/expiring")
async def get_expiring_items(
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(get_current_active_user)
):
    tenant_id_str = str(get_tenant_uuid())
    
    try:
        from datetime import timedelta
        
        cutoff_date = date.today() + timedelta(days=days)
        
        with get_db_session() as session:
            query = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.tenant_id == tenant_id_str,
                    InventoryItemModel.expiry_date <= cutoff_date
                )
            )
            
            # Get total count for pagination
            total = query.count()
            
            # Apply pagination
            items = query.order_by(InventoryItemModel.expiry_date.asc()).offset((page - 1) * limit).limit(limit).all()
            
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
            
            total_pages = (total + limit - 1) // limit if total > 0 else 1
            
            return {
                "alerts": alerts,
                "count": total,
                "days_ahead": days,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
    except Exception as e:
        raise_internal_server_error(f"Error fetching expiring items: {e}")
